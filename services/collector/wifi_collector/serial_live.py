"""Live serial frame source: two independent reader tasks with reconnect."""

from __future__ import annotations

import asyncio
import contextlib
import threading
from collections.abc import AsyncIterator, Callable
from datetime import UTC, datetime
from typing import Any

import serial
from wifi_contracts import NormalizedCsiFrame, SourceHealth, SourceManifest

from wsc_wire.wire_protocol import FRAME_TYPE_DATA, FRAME_TYPE_STATUS, FrameParser

from .wire_conversion import normalized_from_wire_frame

TransportFactory = Callable[[str, int], Any]


def _default_transport(port: str, baud: int) -> serial.Serial:
    return serial.Serial(port=port, baudrate=baud, timeout=0.05)


class SerialLiveFrameSource:
    """Reads two serial ports and yields normalized frames.

    Ports are explicit; the source never guesses devices. Each link runs its
    own reader thread. A dropped link degrades health; reconnects start a new
    epoch and reset the parser so stale seqs cannot be mispaired.
    """

    def __init__(
        self,
        *,
        session_id: str,
        rx_a_port: str,
        rx_b_port: str,
        baud: int = 921600,
        transport_factory: TransportFactory = _default_transport,
        reconnect_min_s: float = 0.5,
        reconnect_max_s: float = 30.0,
        outbox_size: int = 10_000,
    ) -> None:
        if not rx_a_port or not rx_b_port:
            raise ValueError("rx_a_port and rx_b_port must be explicit")
        self.session_id = session_id
        self._ports = {"rx-a": rx_a_port, "rx-b": rx_b_port}
        self._baud = baud
        self._transport_factory = transport_factory
        self._reconnect_min_s = reconnect_min_s
        self._reconnect_max_s = reconnect_max_s
        self._outbox: asyncio.Queue[NormalizedCsiFrame] = asyncio.Queue(
            maxsize=outbox_size
        )
        self._event_queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue(maxsize=1000)
        self._loop: asyncio.AbstractEventLoop | None = None
        self._threads: list[threading.Thread] = []
        self._stop = threading.Event()
        self._paused = asyncio.Event()
        self._paused.set()
        self._closed = False
        self._started_at = datetime.now(UTC)
        self._link_epoch: dict[str, int] = {"rx-a": 0, "rx-b": 0}
        self._link_up: dict[str, bool] = {"rx-a": False, "rx-b": False}
        self._counters: dict[str, int] = {}

    async def open(self) -> SourceManifest:
        self._loop = asyncio.get_running_loop()
        for link_id, port in self._ports.items():
            thread = threading.Thread(
                target=self._reader_loop,
                args=(link_id, port),
                name=f"serial-{link_id}",
                daemon=True,
            )
            thread.start()
            self._threads.append(thread)
        return SourceManifest(
            schema_version="wifi-source.v1",
            session_id=self.session_id,
            source_mode="live",
            session_started_at=self._started_at,
            link_ids=list(self._ports.keys()),
            firmware_versions={"firmware": "wifi-spatial-council-fw/0.1.0"},
            topology_hash="sha256:" + "0" * 64,  # filled by calibration phase
            replay_ref=None,
        )

    def _reader_loop(self, link_id: str, port: str) -> None:
        backoff = self._reconnect_min_s
        parser = FrameParser()
        while not self._stop.is_set():
            transport = None
            try:
                transport = self._transport_factory(port, self._baud)
                self._link_up[link_id] = True
                self._link_epoch[link_id] += 1
                backoff = self._reconnect_min_s
                self._push_event(
                    "source.reconnect",
                    {
                        "link": link_id,
                        "epoch": self._link_epoch[link_id],
                    },
                )
                while not self._stop.is_set():
                    data = transport.read(4096)
                    if not data:
                        continue
                    for parsed in parser.feed(data):
                        if parsed.header.frame_type == FRAME_TYPE_DATA:
                            frame = normalized_from_wire_frame(
                                parsed,
                                session_id=self.session_id,
                                source_mode="live",
                            )
                            self._push_frame(frame)
                        elif parsed.header.frame_type == FRAME_TYPE_STATUS:
                            self._counters[f"{link_id}.status"] = (
                                self._counters.get(f"{link_id}.status", 0) + 1
                            )
            except Exception as exc:  # SerialException, OSError, ...
                self._link_up[link_id] = False
                self._counters[f"{link_id}.reconnects"] = (
                    self._counters.get(f"{link_id}.reconnects", 0) + 1
                )
                self._push_event(
                    "source.link_down",
                    {"link": link_id, "error": str(exc)},
                )
                if transport is not None:
                    with contextlib.suppress(Exception):
                        transport.close()
                # A reconnect is a new epoch: reset the parser so stale
                # partial frames cannot be mispaired across epochs.
                parser = FrameParser()
                self._stop.wait(backoff)
                backoff = min(backoff * 2, self._reconnect_max_s)

    def _push_frame(self, frame: NormalizedCsiFrame) -> None:
        loop = self._loop
        if loop is None:
            return
        try:
            loop.call_soon_threadsafe(self._outbox.put_nowait, frame)
        except asyncio.QueueFull:
            self._counters["outbox_overflow"] = (
                self._counters.get("outbox_overflow", 0) + 1
            )

    def _push_event(self, event_type: str, payload: dict[str, Any]) -> None:
        loop = self._loop
        if loop is None:
            return
        loop.call_soon_threadsafe(
            self._event_queue.put_nowait,
            {"type": event_type, "payload": payload},
        )

    async def frames(self) -> AsyncIterator[NormalizedCsiFrame]:
        while not self._closed:
            await self._paused.wait()
            try:
                frame = await asyncio.wait_for(self._outbox.get(), timeout=0.1)
                yield frame
            except TimeoutError:
                continue

    async def events(self) -> AsyncIterator[dict[str, Any]]:
        """Lifecycle/health events (reconnect, link down) from reader threads."""
        while not self._closed:
            try:
                yield await asyncio.wait_for(self._event_queue.get(), timeout=0.1)
            except TimeoutError:
                continue

    async def pause(self) -> None:
        self._paused.clear()

    async def resume(self) -> None:
        self._paused.set()

    async def close(self) -> None:
        self._closed = True
        self._paused.set()
        self._stop.set()
        for thread in self._threads:
            thread.join(timeout=2.0)

    async def health(self) -> SourceHealth:
        dropped = [link for link, up in self._link_up.items() if not up]
        active = [link for link in self._link_up if self._link_up[link]]
        return SourceHealth(
            schema_version="source-health.v1",
            session_id=self.session_id,
            source_mode="live",
            status="degraded" if dropped else "ok",
            active_links=active,
            degraded_links=dropped,
            dropped_links=dropped,
            counters=dict(self._counters),
            epoch=max(self._link_epoch.values()),
            updated_at=datetime.now(UTC),
        )
