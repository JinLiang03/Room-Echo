"""Labels live only in ground_truth.json; replay and features never see them."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

from wifi_sensing.calibration_session import (
    CalibrationSession,
    labels_for_step,
)


def _fake_hash(label: str) -> str:
    import hashlib

    return "sha256:" + hashlib.sha256(label.encode("utf-8")).hexdigest()


def _session(tmp_path: Path) -> CalibrationSession:
    return CalibrationSession(
        session_id="iso-test",
        profile_id="iso-test",
        room_id="iso-test",
        topology_hash=_fake_hash("topo"),
        board_hashes={"rx-a": _fake_hash("a"), "rx-b": _fake_hash("b")},
        positions={},
        firmware_version="fw",
        estimator_version="estimator-v1",
        root=tmp_path,
        simulated=True,
        seed=1,
    )


def test_ground_truth_is_separate_from_raw_and_events(tmp_path: Path) -> None:
    async def run() -> None:
        session = _session(tmp_path)
        await session.record_trial(
            trial_id="trial-empty-1",
            step="empty_baseline",
            scenario="idle",
            seed=5,
            duration_s=2.0,
            labels=labels_for_step("empty_baseline"),
        )
        await session.record_trial(
            trial_id="trial-walk-1",
            step="standard_motion",
            scenario="walk_through",
            seed=6,
            duration_s=2.0,
            labels=labels_for_step("standard_motion"),
        )

    asyncio.run(run())
    trial_dir = tmp_path / "trials" / "trial-empty-1"
    ground_truth = json.loads(
        (trial_dir / "ground_truth.json").read_text(encoding="utf-8")
    )
    assert ground_truth["schema_version"] == "ground-truth.v1"
    assert ground_truth["labels"]["motion"] == "empty"
    # Labels never appear in raw/events/manifest.
    for name in ("raw.csi.zst", "events.jsonl", "manifest.json"):
        content = (trial_dir / name).read_bytes()
        assert b"ground-truth" not in content
        assert b'"motion"' not in content
    # The replay manifest does not list ground_truth.json.
    manifest = json.loads((trial_dir / "manifest.json").read_text(encoding="utf-8"))
    assert "ground_truth.json" not in manifest["files"]


def test_replay_ignores_ground_truth_file(tmp_path: Path) -> None:
    async def run() -> int:
        session = _session(tmp_path)
        await session.record_trial(
            trial_id="trial-1",
            step="empty_baseline",
            scenario="idle",
            seed=9,
            duration_s=2.0,
            labels=labels_for_step("empty_baseline"),
        )
        from wifi_collector.replay_source import ReplayFrameSource

        source = ReplayFrameSource(tmp_path / "trials" / "trial-1", real_time=False)
        count = 0
        async for _frame in source.frames():
            count += 1
        await source.close()
        return count

    assert asyncio.run(run()) > 0


def test_labels_for_step() -> None:
    assert labels_for_step("occupancy_high")["occupancy_level"] == "high"
    assert labels_for_step("depth_3")["depth_point"] == 3
    assert labels_for_step("empty_baseline")["motion"] == "empty"
