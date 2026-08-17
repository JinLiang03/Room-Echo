"""Calibration sessions: state machine, trial recording, fit, evaluate."""

from __future__ import annotations

import json
import random
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
from wifi_collector.mock_source import MockFrameSource
from wifi_collector.recorder import RecordSession
from wifi_collector.replay_source import ReplayFrameSource
from wifi_contracts import FeatureWindow, NormalizedCsiFrame, SourceManifest

from .calibration import (
    CalibrationMetrics,
    CalibrationProfile,
    ExpiryRules,
    FitParameters,
    fit_profile,
)
from .cleaning import CleanedFrame, CleaningTransformer
from .config import FeatureConfig
from .estimators import depth_score, occupancy_score
from .evaluate import recompute_metrics
from .pipeline import FeaturePipeline
from .trials import GroundTruth, TrialRecord, stratified_trial_split

CAL_STEP_ORDER = [
    "warmup",
    "empty_baseline",
    "standard_motion",
    "occupancy_low",
    "occupancy_medium",
    "occupancy_high",
    "depth_1",
    "depth_2",
    "depth_3",
    "depth_4",
    "depth_5",
    "held_out",
]

TRAIN_STEPS = [
    "empty_baseline",
    "standard_motion",
    "occupancy_low",
    "occupancy_medium",
    "occupancy_high",
    "depth_1",
    "depth_2",
    "depth_3",
    "depth_4",
    "depth_5",
]

STEP_TO_SCENARIO = {
    "warmup": "idle",
    "empty_baseline": "idle",
    "standard_motion": "walk_through",
    "occupancy_low": "occupancy_low",
    "occupancy_medium": "occupancy_medium",
    "occupancy_high": "occupancy_high",
    **{f"depth_{i}": f"depth_{i}" for i in range(1, 6)},
    "held_out": "walk_through",
}


def labels_for_step(step: str) -> dict[str, Any]:
    if step == "empty_baseline":
        return {"motion": "empty", "occupancy_level": None, "depth_point": None}
    if step == "standard_motion":
        return {"motion": "walk", "occupancy_level": None, "depth_point": None}
    if step.startswith("occupancy_"):
        return {
            "motion": None,
            "occupancy_level": step.split("_", 1)[1],
            "depth_point": None,
        }
    if step.startswith("depth_"):
        return {
            "motion": None,
            "occupancy_level": None,
            "depth_point": int(step.split("_", 1)[1]),
        }
    return {"motion": None, "occupancy_level": None, "depth_point": None}


def build_mock_plan(
    *,
    base_seed: int,
    duration_s: float,
    rounds_per_step: int = 2,
) -> list[dict[str, Any]]:
    """Deterministic simulated calibration plan with randomized order."""
    plan: list[dict[str, Any]] = [
        {
            "step": "warmup",
            "scenario": "idle",
            "seed": base_seed,
            "duration_s": min(5.0, duration_s),
            "labels": labels_for_step("warmup"),
        }
    ]
    counter = 0
    for step in TRAIN_STEPS:
        for _round in range(rounds_per_step):
            counter += 1
            plan.append(
                {
                    "step": step,
                    "scenario": STEP_TO_SCENARIO[step],
                    "seed": base_seed + counter,
                    "duration_s": duration_s,
                    "labels": labels_for_step(step),
                }
            )
    for step in TRAIN_STEPS:
        counter += 1
        plan.append(
            {
                "step": step,
                "scenario": STEP_TO_SCENARIO[step],
                "seed": base_seed + 10_000 + counter,
                "duration_s": duration_s,
                "labels": labels_for_step(step),
            }
        )
    rng = random.Random(base_seed)
    order = list(range(len(plan)))
    rng.shuffle(order)
    for position, index in enumerate(order):
        plan[index]["random_order_index"] = position
    return plan


class CalibrationSession:
    """One calibration run; trials are independent raw bundles."""

    def __init__(
        self,
        *,
        session_id: str,
        profile_id: str,
        room_id: str,
        topology_hash: str,
        board_hashes: dict[str, str],
        positions: dict[str, str],
        firmware_version: str,
        estimator_version: str,
        root: Path,
        simulated: bool,
        seed: int,
        environment: str | None = None,
        config: FeatureConfig | None = None,
    ) -> None:
        self.session_id = session_id
        self.profile_id = profile_id
        self.room_id = room_id
        self.topology_hash = topology_hash
        self.board_hashes = board_hashes
        self.positions = positions
        self.firmware_version = firmware_version
        self.estimator_version = estimator_version
        self.root = Path(root)
        self.trials_dir = self.root / "trials"
        self.simulated = simulated
        self.seed = seed
        self.environment = environment
        self.config = config or FeatureConfig()
        self.trials: dict[str, TrialRecord] = {}
        self.state = "created"
        self.profile: CalibrationProfile | None = None
        self.windows_by_trial: dict[str, list[FeatureWindow]] = {}
        self._order_counter = 0

    async def record_trial(
        self,
        *,
        trial_id: str,
        step: str,
        scenario: str,
        seed: int,
        duration_s: float,
        labels: dict[str, Any],
        random_order_index: int | None = None,
    ) -> TrialRecord:
        source = MockFrameSource(
            scenario=scenario,
            seed=seed,
            duration_s=duration_s,
            real_time=False,
            session_id=trial_id,
        )
        recorder = RecordSession(
            source=source,
            session_id=trial_id,
            raw_root=self.trials_dir,
        )
        bundle = await recorder.run()
        await source.close()

        order_index = (
            self._order_counter
            if random_order_index is None
            else random_order_index
        )
        ground_truth = GroundTruth(
            schema_version="ground-truth.v1",
            trial_id=trial_id,
            session_id=self.session_id,
            step=step,
            labels=labels,
            random_order_index=order_index,
            recorded_at=datetime.now(UTC),
            environment=self.environment,
        )
        (bundle / "ground_truth.json").write_text(
            ground_truth.model_dump_json(indent=2) + "\n",
            encoding="utf-8",
        )
        record = TrialRecord(
            trial_id=trial_id,
            step=step,
            bundle_dir=bundle,
            label=labels,
            recorded_at=ground_truth.recorded_at,
            random_order_index=order_index,
        )
        self._order_counter += 1
        self.trials[trial_id] = record
        self.state = self._next_state(step)
        return record

    def _next_state(self, step: str) -> str:
        if step == "held_out":
            return "review"
        index = CAL_STEP_ORDER.index(step)
        return CAL_STEP_ORDER[index + 1]

    async def _frames_for(
        self,
        trial: TrialRecord,
    ) -> tuple[list[NormalizedCsiFrame], SourceManifest]:
        source = ReplayFrameSource(trial.bundle_dir, real_time=False)
        manifest: SourceManifest = await source.open()
        frames: list[NormalizedCsiFrame] = []
        async for frame in source.frames():
            frames.append(frame)
        await source.close()
        return frames, manifest

    async def _cleaned_frames(self, trial_ids: list[str]) -> list[CleanedFrame]:
        cleaner = CleaningTransformer(self.config)
        cleaned: list[CleanedFrame] = []
        for trial_id in trial_ids:
            frames, manifest = await self._frames_for(self.trials[trial_id])
            for frame in frames:
                item = cleaner.clean(frame, manifest)
                if item is not None:
                    cleaned.append(item)
        return cleaned

    async def _windows_for(
        self,
        trial: TrialRecord,
        profile: CalibrationProfile,
    ) -> list[FeatureWindow]:
        frames, manifest = await self._frames_for(trial)
        pipeline = FeaturePipeline(self.config, profile)
        windows: list[FeatureWindow] = []
        for frame in frames:
            windows.extend(pipeline.transform([frame], manifest))
        return windows

    async def fit(self, *, profile_id: str | None = None) -> CalibrationProfile:
        profile_id = profile_id or self.profile_id
        labeled_ids = [
            trial_id
            for trial_id, trial in self.trials.items()
            if trial.step != "warmup"
        ]
        train, validation, test = stratified_trial_split(
            labeled_ids,
            step_of={trial_id: trial.step for trial_id, trial in self.trials.items()},
            seed=self.seed,
        )
        empty_ids = [
            trial_id
            for trial_id in train + validation
            if self.trials[trial_id].step == "empty_baseline"
        ]
        if not empty_ids:
            raise ValueError("fit requires empty_baseline trials in train/validation")
        seed_profile = fit_profile(
            await self._cleaned_frames(empty_ids),
            self.config,
            profile_id=profile_id,
            topology_hash=self.topology_hash,
        )
        self.windows_by_trial = {
            trial_id: await self._windows_for(trial, seed_profile)
            for trial_id, trial in self.trials.items()
        }
        fit_parameters = self._fit_parameters(
            train + validation,
            self.windows_by_trial,
        )
        metrics = self._evaluate(test, self.windows_by_trial, fit_parameters)
        profile = CalibrationProfile.create(
            schema_version="calibration-profile.v1",
            profile_id=profile_id,
            feature_version=self.config.feature_version,
            topology_hash=self.topology_hash,
            room_id=self.room_id,
            board_hashes=self.board_hashes,
            positions=self.positions,
            channel=self.config.expected_channel,
            bandwidth_mhz=self.config.expected_bandwidth_mhz,
            firmware_version=self.firmware_version,
            estimator_version=self.estimator_version,
            environment=self.environment,
            carrier_indices=seed_profile.carrier_indices,
            amplitude_median_db=seed_profile.amplitude_median_db,
            amplitude_mad_db=seed_profile.amplitude_mad_db,
            valid_carriers=seed_profile.valid_carriers,
            fitted_at=datetime.now(UTC),
            source="recorded",
            simulated=self.simulated,
            fit_parameters=fit_parameters,
            training_trial_ids=train,
            validation_trial_ids=validation,
            metrics=metrics,
            expiry=ExpiryRules(),
            state="active",
        )
        self.profile = profile
        self.state = "review"
        return profile

    def _fit_parameters(
        self,
        fit_trial_ids: list[str],
        windows_by_trial: dict[str, list[FeatureWindow]],
    ) -> FitParameters:
        def link_values(step: str, key: str) -> list[float]:
            values = []
            for trial_id in fit_trial_ids:
                if self.trials[trial_id].step != step:
                    continue
                for window in windows_by_trial[trial_id]:
                    for feature in window.links.values():
                        values.append(getattr(feature, key))
            return values

        empty_temporal = link_values("empty_baseline", "temporal_diff_rms")
        walk_temporal = link_values("standard_motion", "temporal_diff_rms")
        p99_empty = float(np.percentile(empty_temporal, 99)) if empty_temporal else 0.0
        p95_walk = float(np.percentile(walk_temporal, 95)) if walk_temporal else 1.0
        scale = 1.0 / max(p95_walk - p99_empty, 1e-9)

        empty_anomaly = link_values("empty_baseline", "amplitude_anomaly_ratio")
        empty_decorrelation = [
            1.0 - value
            for value in link_values("empty_baseline", "shape_correlation_to_baseline")
        ]
        class_scores: dict[str, list[float]] = {}
        for level in ("low", "medium", "high"):
            class_scores[level] = [
                occupancy_score(feature)
                for trial_id in fit_trial_ids
                if self.trials[trial_id].step == f"occupancy_{level}"
                for window in windows_by_trial[trial_id]
                for feature in window.links.values()
            ]
        medians = {
            level: float(np.median(class_scores[level]))
            if class_scores[level]
            else 0.5
            for level in ("low", "medium", "high")
        }
        occupancy_thresholds = {
            "low_medium": (medians["low"] + medians["medium"]) / 2.0,
            "medium_high": (medians["medium"] + medians["high"]) / 2.0,
        }

        depth_medians = []
        for point in range(1, 6):
            scores = []
            for trial_id in fit_trial_ids:
                if self.trials[trial_id].step != f"depth_{point}":
                    continue
                for window in windows_by_trial[trial_id]:
                    score = depth_score(window.paired)
                    if score is not None:
                        scores.append(score)
            depth_medians.append(float(np.median(scores)) if scores else 0.0)
        depth_boundaries = [
            (depth_medians[i] + depth_medians[i + 1]) / 2.0
            for i in range(4)
        ]

        return FitParameters(
            motion_empty_p99_db=round(p99_empty, 6),
            motion_walk_p95_db=round(p95_walk, 6),
            motion_scale=round(scale, 6),
            occupancy_anomaly_baseline=round(
                float(np.median(empty_anomaly)) if empty_anomaly else 0.0, 6
            ),
            occupancy_decorrelation_baseline=round(
                float(np.median(empty_decorrelation))
                if empty_decorrelation
                else 0.0,
                6,
            ),
            occupancy_thresholds={
                key: round(value, 6) for key, value in occupancy_thresholds.items()
            },
            depth_zone_boundaries=[round(value, 6) for value in depth_boundaries],
            depth_single_rx_unknown=True,
        )

    def _evaluate(
        self,
        test_ids: list[str],
        windows_by_trial: dict[str, list[FeatureWindow]],
        fit: FitParameters,
    ) -> CalibrationMetrics:
        return recompute_metrics(
            fit,
            simulated=self.simulated,
            test_trial_ids=test_ids,
            windows_by_trial=windows_by_trial,
            step_of={trial_id: trial.step for trial_id, trial in self.trials.items()},
        )

    def activate(self) -> CalibrationProfile:
        if self.profile is None:
            raise ValueError("cannot activate before fit")
        if self.state != "review":
            raise ValueError(f"cannot activate from state {self.state!r}")
        self.state = "active"
        self.profile.state = "active"
        return self.profile

    def invalidate(self, reason: str) -> None:
        self.state = "failed"
        if self.profile is not None:
            self.profile.state = "failed"
        (self.root / "invalidation.json").write_text(
            json.dumps(
                {"reason": reason, "at": datetime.now(UTC).isoformat()},
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

    def trials_manifest(self) -> dict[str, dict[str, Any]]:
        return {
            trial_id: {
                "trial_id": trial_id,
                "step": trial.step,
                "bundle_dir": str(trial.bundle_dir.relative_to(self.root)),
                "labels": trial.label,
                "random_order_index": trial.random_order_index,
                "recorded_at": trial.recorded_at.isoformat(),
            }
            for trial_id, trial in self.trials.items()
        }
