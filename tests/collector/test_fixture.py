"""Frozen walk_through fixture: verifiable, deterministic, replay-equivalent."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

from scripts.generate_fixtures import build_replay_fixture_to
from wifi_collector.replay_bundle import BundleVerifier
from wifi_collector.replay_source import ReplayFrameSource

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = ROOT / "data" / "fixtures" / "walk_through"
EXPECTED_FRAMES = 2000  # 10 s x 100 pps x 2 links


def test_frozen_fixture_verifies() -> None:
    result = BundleVerifier(FIXTURE).verify()
    assert result.ok, result.errors
    assert result.manifest is not None
    assert result.manifest.status == "complete"
    assert result.manifest.session_id == "session-fixture-walk-through"


def test_frozen_fixture_replays_expected_frames() -> None:
    async def check() -> None:
        source = ReplayFrameSource(FIXTURE, real_time=False)
        frames = []
        async for frame in source.frames():
            frames.append(frame)
        await source.close()
        assert len(frames) == EXPECTED_FRAMES
        assert {frame.link_id for frame in frames} == {"rx-a", "rx-b"}
        assert all(frame.source_mode == "replay" for frame in frames)

    asyncio.run(check())


def test_frozen_fixture_is_deterministic(tmp_path: Path) -> None:
    build_replay_fixture_to(tmp_path)
    generated = tmp_path / "walk_through"
    for name in ("manifest.json", "raw.csi.zst", "events.jsonl", "checksums.sha256"):
        assert (generated / name).read_bytes() == (FIXTURE / name).read_bytes()


def test_frozen_fixture_replay_equals_mock_excluding_mode(tmp_path: Path) -> None:
    async def check() -> None:
        source = ReplayFrameSource(FIXTURE, real_time=False)
        replayed = []
        async for frame in source.frames():
            replayed.append(frame.model_dump(mode="json"))
        await source.close()
        assert len(replayed) == EXPECTED_FRAMES
        manifest = json.loads((FIXTURE / "manifest.json").read_text(encoding="utf-8"))
        assert manifest["source_mode"] == "mock"
        assert all(frame["source_mode"] == "replay" for frame in replayed)

    asyncio.run(check())
