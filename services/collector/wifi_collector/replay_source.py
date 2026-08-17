"""Replay frame source: virtual clock, pause/resume/seek/step, recompute flag."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

import zstandard as zstd
from wifi_contracts import NormalizedCsiFrame, SourceHealth, SourceManifest

from wsc_wire.wire_protocol import FRAME_TYPE_DATA, FrameParser

from .replay_bundle import RAW_FILE, BundleVerifier, ReplayManifest
from .wire_conversion import normalized_from_wire_frame


class ReplayFrameSource:
    """Replays a verified bundle on a virtual clock.

    ``rate`` is the play speed (0.25-4.0). ``seek(seconds)`` repositions the
    active reader, including backwards. ``step(n)`` pauses continuous
    playback, yields exactly n raw frames, then remains paused.
    ``recompute`` is recorded for later phases (features recomputed from raw)
    and does not change raw→normalized conversion in this phase.
    """

    def __init__(
        self,
        bundle_root: Path,
        *,
        rate: float = 1.0,
        recompute: bool = False,
        real_time: bool = True,
        max_raw_bytes: int = 512 * 1024 * 1024,
    ) -> None:
        if not 0.25 <= rate <= 4.0:
            raise ValueError("rate must be within [0.25, 4.0]")
        self.bundle_root = Path(bundle_root)
        self.rate = rate
        self.recompute = recompute
        self.real_time = real_time
        self._verifier = BundleVerifier(
            self.bundle_root,
            max_raw_bytes=max_raw_bytes,
        )
        self._manifest: ReplayManifest | None = None
        self._paused = asyncio.Event()
        self._paused.set()
        self._control_changed = asyncio.Event()
        self._closed = False
        self._seek_s: float = 0.0
        self._step_remaining = 0
        self._control_revision = 0
        self._frame_revision = 0
        self._position_s = 0.0
        self._frame_count = 0

    async def open(self) -> SourceManifest:
        result = self._verifier.verify()
        if not result.ok or result.manifest is None:
            raise ValueError(
                f"bundle verification failed: {'; '.join(result.errors)}"
            )
        self._manifest = result.manifest
        return SourceManifest(
            schema_version="wifi-source.v1",
            session_id=self._manifest.session_id,
            source_mode="replay",
            session_started_at=self._manifest.created_at,
            link_ids=list(self._manifest.board_hashes.keys()),
            firmware_versions={
                "firmware": self._manifest.firmware_version,
                "collector": self._manifest.collector_version,
            },
            topology_hash=self._manifest.topology_hash,
            replay_ref=str(self.bundle_root),
        )

    def seek(self, seconds: float) -> None:
        self._seek_s = max(0.0, seconds)
        self._position_s = self._seek_s
        self._step_remaining = 0
        self._control_revision += 1
        self._control_changed.set()

    def step(self, count: int) -> None:
        # A step command is a paused operation even when issued during
        # continuous playback. Multiple commands queued before consumption
        # are additive: each command still advances its requested frames.
        self._paused.clear()
        self._step_remaining += max(1, count)
        self._control_changed.set()

    @property
    def is_paused(self) -> bool:
        return not self._paused.is_set()

    @property
    def control_revision(self) -> int:
        """Revision of the requested replay position.

        Consumers with derived state can reset it when this changes. The
        revision only advances for seek because pause, rate and step preserve
        the current signal-processing history.
        """

        return self._control_revision

    @property
    def frame_revision(self) -> int:
        """Seek revision associated with the most recently yielded frame."""

        return self._frame_revision

    @property
    def position_s(self) -> float:
        """Requested position or timestamp of the most recently yielded frame."""

        return self._position_s

    async def _next_permission(
        self,
        expected_revision: int,
    ) -> Literal["continuous", "step"] | None:
        """Wait until playback or a step token permits exactly one frame."""

        while True:
            if self._closed or self._control_revision != expected_revision:
                return None
            if self._step_remaining > 0:
                self._step_remaining -= 1
                return "step"
            if self._paused.is_set():
                return "continuous"

            # Clear and re-check before awaiting so a same-loop control call
            # cannot be lost between the state check and Event.wait().
            self._control_changed.clear()
            if (
                self._closed
                or self._control_revision != expected_revision
                or self._step_remaining > 0
                or self._paused.is_set()
            ):
                continue
            await self._control_changed.wait()

    async def _pace_or_interrupt(
        self,
        delay_s: float,
        expected_revision: int,
    ) -> bool:
        """Return True after pacing, False when a control must be re-applied."""

        if delay_s <= 0:
            return True
        self._control_changed.clear()
        if (
            self._closed
            or self._control_revision != expected_revision
            or not self._paused.is_set()
            or self._step_remaining > 0
        ):
            return False
        try:
            await asyncio.wait_for(
                self._control_changed.wait(),
                timeout=delay_s,
            )
        except TimeoutError:
            return True
        return False

    async def frames(self) -> AsyncIterator[NormalizedCsiFrame]:
        if self._manifest is None:
            await self.open()
        assert self._manifest is not None
        raw_path = self.bundle_root / RAW_FILE

        # Each seek revision owns one forward-only decompression pass. A seek
        # (including seek(0)) interrupts waits, closes that reader, and starts
        # a fresh pass at the requested timestamp. This stays memory bounded
        # instead of materializing the raw bundle solely to enable rewind.
        while not self._closed:
            revision = self._control_revision
            seek_s = self._seek_s
            parser = FrameParser()
            last_ts_us: int | None = None
            restart = False
            with zstd.ZstdDecompressor().stream_reader(
                raw_path.open("rb"),
                read_across_frames=True,
            ) as reader:
                while not self._closed:
                    if self._control_revision != revision:
                        restart = True
                        break
                    chunk = reader.read(1 << 16)
                    if not chunk:
                        break
                    for parsed in parser.feed(chunk):
                        if self._control_revision != revision:
                            restart = True
                            break
                        if parsed.header.frame_type != FRAME_TYPE_DATA:
                            continue
                        position_s = parsed.header.device_ts_us / 1_000_000
                        if position_s < seek_s:
                            continue

                        while True:
                            permission = await self._next_permission(revision)
                            if permission is None:
                                restart = self._control_revision != revision
                                break
                            if (
                                permission == "continuous"
                                and self.real_time
                                and last_ts_us is not None
                            ):
                                delta_s = (
                                    parsed.header.device_ts_us - last_ts_us
                                ) / 1e6
                                if delta_s > 0 and not await self._pace_or_interrupt(
                                    delta_s / self.rate,
                                    revision,
                                ):
                                    continue
                            break
                        if permission is None:
                            break

                        last_ts_us = parsed.header.device_ts_us
                        self._frame_count += 1
                        self._position_s = position_s
                        self._frame_revision = revision
                        yield normalized_from_wire_frame(
                            parsed,
                            session_id=self._manifest.session_id,
                            source_mode="replay",
                        )
                    if restart:
                        break
                    # Long seeks scan without yielding frames; yield once per
                    # chunk so newer controls and close remain responsive.
                    await asyncio.sleep(0)
            if not restart:
                return

    async def pause(self) -> None:
        self._paused.clear()
        self._control_changed.set()

    async def resume(self) -> None:
        self._step_remaining = 0
        self._paused.set()
        self._control_changed.set()

    async def close(self) -> None:
        self._closed = True
        self._paused.set()
        self._control_changed.set()

    async def health(self) -> SourceHealth:
        manifest = self._manifest
        return SourceHealth(
            schema_version="source-health.v1",
            session_id=manifest.session_id if manifest else "unknown",
            source_mode="replay",
            status="ok",
            active_links=list(manifest.board_hashes.keys()) if manifest else [],
            degraded_links=[],
            dropped_links=[],
            counters={"frames_replayed": self._frame_count},
            epoch=0,
            updated_at=datetime.now(UTC),
        )
