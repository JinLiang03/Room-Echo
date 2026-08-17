"""Mock calibration: fit/evaluate reproducible and separable on held-out."""

from __future__ import annotations

import asyncio
from pathlib import Path

from wifi_sensing.calibration_session import CalibrationSession, build_mock_plan


def _session(tmp_path: Path, seed: int) -> CalibrationSession:
    return CalibrationSession(
        session_id=f"fit-{seed}",
        profile_id="fit-test",
        room_id="fit-test",
        topology_hash="sha256:" + "a" * 64,
        board_hashes={},
        positions={},
        firmware_version="fw",
        estimator_version="estimator-v1",
        root=tmp_path,
        simulated=True,
        seed=seed,
    )


async def _fit(tmp_path: Path, seed: int):
    session = _session(tmp_path, seed)
    plan = build_mock_plan(base_seed=seed, duration_s=2.5)
    for index, item in enumerate(plan):
        await session.record_trial(
            trial_id=f"t-{seed}-{index:03d}",
            **item,
        )
    profile = await session.fit()
    session.activate()
    return profile


def test_mock_fit_produces_signed_simulated_profile(tmp_path: Path) -> None:
    profile = asyncio.run(_fit(tmp_path, 11))
    assert profile.simulated is True
    assert profile.verify_integrity()
    assert profile.state == "active"
    assert profile.fit_parameters is not None
    assert profile.metrics is not None
    assert profile.metrics.simulated is True


def test_mock_held_out_metrics_separate_classes(tmp_path: Path) -> None:
    profile = asyncio.run(_fit(tmp_path, 23))
    metrics = profile.metrics
    assert metrics is not None
    assert metrics.motion_separation > 0.3
    assert metrics.occupancy_ordinal_accuracy > 0.4
    assert metrics.depth_monotonic_accuracy > 0.4
    assert len(metrics.held_out_trial_ids) > 0


def test_mock_fit_is_reproducible(tmp_path: Path) -> None:
    first = asyncio.run(_fit(tmp_path / "a", 42))
    second = asyncio.run(_fit(tmp_path / "b", 42))
    assert first.fit_parameters == second.fit_parameters
    assert first.training_trial_ids == second.training_trial_ids
    assert first.validation_trial_ids == second.validation_trial_ids
    first_metrics = first.metrics.model_dump(exclude={"evaluated_at"})
    second_metrics = second.metrics.model_dump(exclude={"evaluated_at"})
    assert first_metrics == second_metrics
