"""Model card: inputs, outputs, training scenarios, limitations."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .calibration import CalibrationProfile
from .signal_config import SignalConfig


def build_model_card(
    profile: CalibrationProfile,
    signal_config: SignalConfig,
    *,
    source: str,
    metrics: dict[str, Any] | None = None,
) -> dict[str, Any]:
    fit = profile.fit_parameters
    return {
        "schema_version": "model-card.v1",
        "estimator": "baseline-v1 (motion scale / occupancy ordinal / depth zones)",
        "estimator_version": f"{signal_config.version}/{profile.estimator_version}/{profile.feature_version}",
        "source": source,
        "simulated": profile.simulated,
        "inputs": [
            "FeatureWindow per link: temporal_diff_rms, anomaly ratio, shape correlation, spectral bands, valid carriers, paired coverage",
        ],
        "outputs": [
            "motion_intensity 0..1 + state",
            "occupancy_density_proxy low/medium/high/unknown probabilities",
            "depth_zone_proxy near/mid/far/unknown probabilities",
            "signal-level quality + sensor_confidence_cap",
        ],
        "training_scenarios": [
            step for step in (
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
            )
        ],
        "unknown_conditions": [
            "single RX for depth (always unknown)",
            "single RX for occupancy when trained on dual links",
            "fast motion freezes occupancy (motion is not density)",
            "profile/topology mismatch",
            "paired coverage below threshold",
            "insufficient quality (packet/carrier/clock/calibration)",
            "staleness (estimate_stale clears previous state)",
        ],
        "limitations": [
            "occupancy labels are scene disturbance grades, not person counts",
            "depth zones are ordinal along the preset axis, not metric depth",
            "simulated metrics are not hardware evidence" if profile.simulated
            else "metrics from real hardware",
            "no cross-RX phase, AoA, or ToF (ADR 0003)",
        ],
        "evaluation": metrics or {},
        "fit_parameters": fit.model_dump() if fit else None,
        "profile_checksum": profile.checksum,
    }


def write_model_card(card: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(card, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
