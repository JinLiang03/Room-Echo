"""Quality precheck gates for trials."""

from __future__ import annotations

import asyncio
from pathlib import Path

from wifi_sensing.calibration_session import CalibrationSession
from wifi_sensing.quality import check_trial_quality


def _session(tmp_path: Path) -> CalibrationSession:
    return CalibrationSession(
        session_id="q-test",
        profile_id="q-test",
        room_id="q-test",
        topology_hash="sha256:" + "0" * 64,
        board_hashes={},
        positions={},
        firmware_version="fw",
        estimator_version="estimator-v1",
        root=tmp_path,
        simulated=True,
        seed=1,
    )


def test_clean_trial_passes_precheck(tmp_path: Path) -> None:
    async def run() -> tuple[bool, list[str]]:
        session = _session(tmp_path)
        record = await session.record_trial(
            trial_id="clean",
            step="empty_baseline",
            scenario="idle",
            seed=1,
            duration_s=2.5,
            labels={},
        )
        return await check_trial_quality(record.bundle_dir)

    ok, reasons = asyncio.run(run())
    assert ok, reasons


def test_packet_loss_trial_fails_precheck(tmp_path: Path) -> None:
    async def run() -> tuple[bool, list[str]]:
        session = _session(tmp_path)
        record = await session.record_trial(
            trial_id="lossy",
            step="empty_baseline",
            scenario="packet_loss",
            seed=2,
            duration_s=2.5,
            labels={},
        )
        return await check_trial_quality(record.bundle_dir)

    ok, reasons = asyncio.run(run())
    assert not ok
    assert "low_packet_coverage" in reasons
