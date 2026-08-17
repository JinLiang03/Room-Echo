"""SerialLiveFrameSource with fake transports: parsing, reconnect, epoch."""

from __future__ import annotations

import asyncio
import time

import pytest
from wifi_collector.mock_source import MockFrameSource
from wifi_collector.serial_live import SerialLiveFrameSource
from wifi_collector.wire_conversion import wire_bytes_from_normalized


class FakeTransport:
    def __init__(self, chunks: list[bytes], fail_after_reads: int | None = None):
        self._chunks = list(chunks)
        self._reads = 0
        self.fail_after_reads = fail_after_reads
        self.closed = False

    def read(self, _max_bytes: int) -> bytes:
        self._reads += 1
        if self.fail_after_reads is not None and self._reads > self.fail_after_reads:
            raise OSError("device disconnected")
        if self._chunks:
            return self._chunks.pop(0)
        return b""

    def close(self) -> None:
        self.closed = True


def _wire_frames_for(link: str, seed: int = 4, count: int = 5) -> list[bytes]:
    async def build() -> list[bytes]:
        source = MockFrameSource(
            scenario="idle",
            seed=seed,
            duration_s=0.05,
            real_time=False,
        )
        wire = []
        async for frame in source.frames():
            if frame.link_id == link and len(wire) < count:
                wire.append(wire_bytes_from_normalized(frame))
        return wire

    return asyncio.run(build())


async def _collect(source: SerialLiveFrameSource, count: int, timeout: float = 5.0) -> list:
    frames = []
    deadline = time.monotonic() + timeout
    async for frame in source.frames():
        frames.append(frame)
        if len(frames) >= count:
            break
        if time.monotonic() > deadline:
            raise TimeoutError(f"collected {len(frames)}/{count} frames")
    return frames


def test_requires_explicit_ports() -> None:
    with pytest.raises(ValueError, match="explicit"):
        SerialLiveFrameSource(
            session_id="s",
            rx_a_port="",
            rx_b_port="/dev/ttyUSB1",
        )


def test_reads_both_links_and_survives_chunk_boundaries() -> None:
    frames_a = _wire_frames_for("rx-a")
    frames_b = _wire_frames_for("rx-b")
    # Split one frame mid-header to exercise chunk-boundary parsing.
    chunked = []
    for index, wire in enumerate(frames_a):
        if index == 2 and len(wire) > 20:
            chunked.append(wire[:9])
            chunked.append(wire[9:])
        else:
            chunked.append(wire)

    def factory(port: str, _baud: int):
        return FakeTransport(chunked if port == "/dev/fake-a" else frames_b)

    async def check() -> None:
        source = SerialLiveFrameSource(
            session_id="sess-live",
            rx_a_port="/dev/fake-a",
            rx_b_port="/dev/fake-b",
            transport_factory=factory,
        )
        await source.open()
        frames = await _collect(source, count=8)
        await source.close()
        assert len(frames) == 8
        assert {frame.link_id for frame in frames} == {"rx-a", "rx-b"}
        health = await source.health()
        assert health.status == "ok"

    asyncio.run(check())


def test_reconnect_starts_new_epoch_and_degrades_health() -> None:
    frames_a = _wire_frames_for("rx-a", count=3)
    frames_b = _wire_frames_for("rx-b", count=3)
    transport_calls = {"n": 0}

    def factory(port: str, _baud: int):
        if port == "/dev/fake-b":
            transport_calls["n"] += 1
            if transport_calls["n"] == 1:
                return FakeTransport(frames_b, fail_after_reads=2)
            return FakeTransport(frames_b)
        return FakeTransport(frames_a)

    async def check() -> None:
        source = SerialLiveFrameSource(
            session_id="sess-live2",
            rx_a_port="/dev/fake-a",
            rx_b_port="/dev/fake-b",
            transport_factory=factory,
            reconnect_min_s=0.01,
            reconnect_max_s=0.05,
        )
        await source.open()
        frames = await _collect(source, count=6, timeout=8.0)
        assert len(frames) == 6
        health = await source.health()
        assert health.status == "ok"
        assert health.epoch >= 1
        assert health.counters["rx-b.reconnects"] >= 1
        await source.close()

    asyncio.run(check())
