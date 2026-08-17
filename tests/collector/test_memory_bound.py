"""10-minute synthetic stream: parser and recorder stay bounded."""

from __future__ import annotations

import asyncio
import gc
import tracemalloc
from pathlib import Path

from wifi_collector.mock_source import MockFrameSource
from wifi_collector.raw_writer import RawBundleWriter
from wifi_collector.replay_bundle import ReplayManifest
from wifi_collector.wire_conversion import wire_bytes_from_normalized

from wsc_wire.wire_protocol import FRAME_MAX_LEN, FrameParser


def test_ten_minute_stream_memory_bounded(tmp_path: Path) -> None:
    async def run() -> tuple[int, int]:
        source = MockFrameSource(
            scenario="walk_through",
            seed=123,
            rate_hz=50,
            duration_s=600.0,  # 10 simulated minutes
            real_time=False,
            session_id="sess-mem",
        )
        manifest = ReplayManifest(
            schema_version="replay-manifest.v1",
            recording_id="sess-mem",
            session_id="sess-mem",
            created_at=source._started_at,
            source_mode="mock",
            firmware_version="0.0.0-mock",
            collector_version="0.1.0",
            contracts_version="1.0.0",
            board_hashes={"rx-a": "sha256:" + "a" * 64, "rx-b": "sha256:" + "b" * 64},
            topology_hash="sha256:" + "c" * 64,
            channel=6,
            bandwidth_mhz=20,
            files=[],
            privacy="memory-bound test",
            status="incomplete",
        )
        writer = RawBundleWriter(
            session_id="sess-mem",
            raw_root=tmp_path,
            manifest=manifest,
        )
        writer.start()
        parser = FrameParser()
        max_buffer = 0
        count = 0
        try:
            async for frame in source.frames():
                wire = wire_bytes_from_normalized(frame)
                writer.append_wire_frame(wire)
                parser.feed(wire)
                max_buffer = max(max_buffer, len(parser._buffer))
                count += 1
            writer.finalize()
        finally:
            await source.close()
        return count, max_buffer

    gc.collect()
    tracemalloc.start()
    try:
        count, max_buffer = asyncio.run(run())
        gc.collect()
        current, _peak = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()

    assert current < 100 * 1024 * 1024
    assert max_buffer <= FRAME_MAX_LEN + 4
    assert count == 60_000  # 600 s x 50 pps x 2 links
    assert (tmp_path / "sess-mem" / "raw.csi.zst").is_file()
