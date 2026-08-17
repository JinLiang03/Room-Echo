"""Wire ↔ NormalizedCsiFrame conversion round-trips."""

from __future__ import annotations

import asyncio

from wifi_collector.mock_source import MockFrameSource
from wifi_collector.wire_conversion import (
    normalized_from_wire_frame,
    tx_id_hash_to_u64,
    u64_to_tx_id_hash,
    wire_bytes_from_normalized,
)

from wsc_wire.wire_protocol import FRAME_TYPE_DATA, FrameParser


def _sample_frames() -> list:
    async def collect() -> list:
        source = MockFrameSource(
            scenario="walk_through",
            seed=5,
            duration_s=0.2,
            real_time=False,
        )
        frames = []
        async for frame in source.frames():
            frames.append(frame)
        return frames

    return asyncio.run(collect())


def test_round_trip_preserves_wire_fields() -> None:
    for original in _sample_frames():
        wire = wire_bytes_from_normalized(original)
        parsed = FrameParser().feed(wire)
        assert len(parsed) == 1
        assert parsed[0].header.frame_type == FRAME_TYPE_DATA
        restored = normalized_from_wire_frame(
            parsed[0],
            session_id=original.session_id,
            source_mode=original.source_mode,
        )
        assert restored.model_dump(mode="json") == original.model_dump(mode="json")


def test_tx_id_hash_round_trip() -> None:
    value = u64_to_tx_id_hash(0x0123456789ABCDEF)
    assert tx_id_hash_to_u64(value) == 0x0123456789ABCDEF
    # Non-fnv strings are hashed deterministically.
    a = tx_id_hash_to_u64("sha256:abcd")
    b = tx_id_hash_to_u64("sha256:abcd")
    assert a == b
    assert a != tx_id_hash_to_u64("sha256:abce")
