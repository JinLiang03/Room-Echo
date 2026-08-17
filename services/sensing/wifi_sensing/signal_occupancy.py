"""Occupancy / obstruction coverage proxy estimator."""

from __future__ import annotations

from dataclasses import dataclass, field

from wifi_contracts import FeatureWindow

from .calibration import CalibrationProfile
from .estimators import occupancy_bin, occupancy_score
from .signal_config import SignalConfig

_BIN_PROBS = {
    "low": (0.80, 0.15, 0.05),
    "medium": (0.15, 0.70, 0.15),
    "high": (0.05, 0.15, 0.80),
}


@dataclass
class OccupancyResult:
    probabilities: dict[str, float]
    state: str
    confidence: float
    flags: list[str] = field(default_factory=list)


class OccupancyEstimator:
    """Low-frequency anomaly + shape decorrelation mapped through the
    profile's ordinal thresholds. Fast motion freezes the estimate (motion is
    never read as density). Single-RX windows are unknown when the profile
    was trained on dual links."""

    def __init__(
        self,
        config: SignalConfig,
        profile: CalibrationProfile,
    ) -> None:
        self.config = config
        self.profile = profile

    def estimate(
        self,
        window: FeatureWindow,
        quality: float,
        motion_value: float | None,
    ) -> OccupancyResult:
        fit = self.profile.fit_parameters
        flags: list[str] = []
        if fit is None:
            return self._unknown(["no_fit_parameters"])
        if quality < self.config.unavailable_quality:
            return self._unknown(["insufficient_quality"])
        if len(window.links) < 2:
            return self._unknown(["single_link"])
        if (
            motion_value is not None
            and motion_value >= self.config.occupancy_motion_freeze
        ):
            return self._unknown(["motion_contamination"])

        scores = [
            occupancy_score(feature) for feature in window.links.values()
        ]
        score = max(scores) if scores else 0.0
        bin_label = occupancy_bin(score, fit)
        confidence = min(1.0, quality)
        p_unknown = 1.0 - confidence
        low, medium, high = _BIN_PROBS[bin_label]
        scale = 1.0 - p_unknown
        low_r = round(low * scale, 6)
        medium_r = round(medium * scale, 6)
        high_r = round(high * scale, 6)
        probabilities = {
            "low": low_r,
            "medium": medium_r,
            "high": high_r,
            "unknown": round(1.0 - (low_r + medium_r + high_r), 6),
        }
        return OccupancyResult(
            probabilities=probabilities,
            state=bin_label,
            confidence=round(confidence, 6),
            flags=flags,
        )

    def _unknown(self, flags: list[str]) -> OccupancyResult:
        return OccupancyResult(
            probabilities={"low": 0.0, "medium": 0.0, "high": 0.0, "unknown": 1.0},
            state="unknown",
            confidence=0.0,
            flags=flags,
        )
