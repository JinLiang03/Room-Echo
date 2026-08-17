"""Calibration trials: ground truth, recording records, stratified split."""

from __future__ import annotations

import random
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class GroundTruth(BaseModel):
    """Labels live only in ground_truth.json; never in raw/events/features.

    occupancy_level is a scene disturbance grade, NOT a person count.
    depth_point is an ordinal point along the preset axis, NOT metric depth.
    """

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["ground-truth.v1"] = "ground-truth.v1"
    trial_id: str = Field(min_length=1)
    session_id: str = Field(min_length=1)
    step: str = Field(min_length=1)
    labels: dict[str, Any]
    random_order_index: int = Field(ge=0)
    recorded_at: datetime
    environment: str | None = None


@dataclass
class TrialRecord:
    trial_id: str
    step: str
    bundle_dir: Path
    label: dict[str, Any]
    recorded_at: datetime
    random_order_index: int


def stratified_trial_split(
    trial_ids: list[str],
    *,
    step_of: dict[str, str],
    seed: int,
) -> tuple[list[str], list[str], list[str]]:
    """Split by trial, stratified per step; never splits a recording's frames."""
    rng = random.Random(seed)
    train: list[str] = []
    validation: list[str] = []
    test: list[str] = []
    steps = sorted({step_of[trial_id] for trial_id in trial_ids})
    for step in steps:
        ids = sorted(trial_id for trial_id in trial_ids if step_of[trial_id] == step)
        rng.shuffle(ids)
        if not ids:
            continue
        test.append(ids.pop())  # one held-out trial per step
        if ids:
            validation.append(ids.pop())
        train.extend(ids)
    return train, validation, test
