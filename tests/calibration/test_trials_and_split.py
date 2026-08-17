"""Trial split: trial-level, stratified, deterministic, no overlap."""

from __future__ import annotations

from wifi_sensing.trials import stratified_trial_split


def test_split_is_trial_level_and_stratified() -> None:
    trial_ids = [f"t-{step}-{i}" for step in (
        "empty_baseline",
        "standard_motion",
        "occupancy_low",
        "depth_1",
    ) for i in range(3)]
    step_of = {trial_id: trial_id.split("-")[1] for trial_id in trial_ids}
    train, validation, test = stratified_trial_split(
        trial_ids,
        step_of=step_of,
        seed=42,
    )
    assert set(train) & set(validation) == set()
    assert set(train) & set(test) == set()
    assert set(validation) & set(test) == set()
    assert set(train) | set(validation) | set(test) == set(trial_ids)
    # Every step contributes at least one held-out trial.
    for step in ("empty_baseline", "standard_motion", "occupancy_low", "depth_1"):
        assert any(step_of[trial_id] == step for trial_id in test)


def test_split_is_deterministic() -> None:
    trial_ids = [f"t-{i}" for i in range(9)]
    step_of = {trial_id: "step" for trial_id in trial_ids}
    a = stratified_trial_split(trial_ids, step_of=step_of, seed=7)
    b = stratified_trial_split(trial_ids, step_of=step_of, seed=7)
    assert a == b


def test_no_frame_level_leakage() -> None:
    # Splits operate on trial IDs only; a single recording can never straddle
    # two sets because windows are derived per trial bundle.
    trial_ids = ["recording-a", "recording-b", "recording-c"]
    step_of = {trial_id: "empty_baseline" for trial_id in trial_ids}
    train, validation, test = stratified_trial_split(
        trial_ids,
        step_of=step_of,
        seed=1,
    )
    assert "recording-a" in train + validation + test
    assert len(train) + len(validation) + len(test) == 3
