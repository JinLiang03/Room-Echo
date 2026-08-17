"""Calibration state machine transitions."""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest
from wifi_sensing.calibration_session import (
    CAL_STEP_ORDER,
    STEP_TO_SCENARIO,
    CalibrationSession,
    labels_for_step,
)


def _session(tmp_path: Path) -> CalibrationSession:
    return CalibrationSession(
        session_id="state-test",
        profile_id="state-test",
        room_id="state-test",
        topology_hash="sha256:" + "0" * 64,
        board_hashes={},
        positions={},
        firmware_version="fw",
        estimator_version="estimator-v1",
        root=tmp_path,
        simulated=True,
        seed=3,
    )


def test_state_machine_progresses_through_steps(tmp_path: Path) -> None:
    async def run() -> list[str]:
        session = _session(tmp_path)
        states = [session.state]
        for index, step in enumerate(CAL_STEP_ORDER):
            await session.record_trial(
                trial_id=f"t-{index}",
                step=step,
                scenario=STEP_TO_SCENARIO[step],
                seed=index,
                duration_s=0.5,
                labels=labels_for_step(step),
            )
            states.append(session.state)
        return states

    states = asyncio.run(run())
    assert states[0] == "created"
    assert states[-1] == "review"
    assert states[-2] == "held_out"


def test_cannot_activate_before_fit(tmp_path: Path) -> None:
    async def run() -> None:
        session = _session(tmp_path)
        await session.record_trial(
            trial_id="t-0",
            step="warmup",
            scenario="idle",
            seed=1,
            duration_s=0.5,
            labels=labels_for_step("warmup"),
        )
        with pytest.raises(ValueError, match="before fit"):
            session.activate()

    asyncio.run(run())


def test_invalidate_marks_failed(tmp_path: Path) -> None:
    session = _session(tmp_path)
    session.invalidate("room moved")
    assert session.state == "failed"
    assert (tmp_path / "invalidation.json").is_file()
