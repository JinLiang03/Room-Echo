"""Held-out evaluation; reusable by fit, CLI, and re-evaluation scripts."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import numpy as np

from .calibration import CalibrationMetrics, FitParameters
from .estimators import (
    depth_bin,
    depth_score,
    motion_score,
    occupancy_bin,
    occupancy_score,
)


def recompute_metrics(
    fit: FitParameters,
    *,
    simulated: bool,
    test_trial_ids: list[str],
    windows_by_trial: dict[str, list[Any]],
    step_of: dict[str, str],
) -> CalibrationMetrics:
    """One-shot metrics on held-out test trials (never used to tune)."""
    motion_empty = [
        motion_score(feature, fit)
        for trial_id in test_trial_ids
        if step_of.get(trial_id) == "empty_baseline"
        for window in windows_by_trial.get(trial_id, [])
        for feature in window.links.values()
    ]
    motion_walk = [
        motion_score(feature, fit)
        for trial_id in test_trial_ids
        if step_of.get(trial_id) == "standard_motion"
        for window in windows_by_trial.get(trial_id, [])
        for feature in window.links.values()
    ]
    motion_separation = (
        float(np.mean(motion_walk)) - float(np.mean(motion_empty))
        if motion_walk and motion_empty
        else 0.0
    )

    occupancy_correct = 0
    occupancy_total = 0
    for trial_id in test_trial_ids:
        step = step_of.get(trial_id, "")
        if not step.startswith("occupancy_"):
            continue
        true_level = step.split("_", 1)[1]
        for window in windows_by_trial.get(trial_id, []):
            for feature in window.links.values():
                occupancy_total += 1
                if occupancy_bin(occupancy_score(feature), fit) == true_level:
                    occupancy_correct += 1
    occupancy_accuracy = (
        occupancy_correct / occupancy_total if occupancy_total else 0.0
    )

    depth_correct = 0
    depth_total = 0
    for trial_id in test_trial_ids:
        step = step_of.get(trial_id, "")
        if not step.startswith("depth_"):
            continue
        true_point = int(step.split("_", 1)[1])
        for window in windows_by_trial.get(trial_id, []):
            depth_total += 1
            if depth_bin(depth_score(window.paired), fit) == true_point:
                depth_correct += 1
    depth_accuracy = depth_correct / depth_total if depth_total else 0.0

    return CalibrationMetrics(
        motion_separation=round(motion_separation, 6),
        occupancy_ordinal_accuracy=round(occupancy_accuracy, 6),
        depth_monotonic_accuracy=round(depth_accuracy, 6),
        held_out_trial_ids=sorted(test_trial_ids),
        evaluated_at=datetime.now(UTC),
        simulated=simulated,
    )
