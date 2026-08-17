"""Motion intensity estimator."""

from __future__ import annotations

from dataclasses import dataclass, field

from wifi_contracts import FeatureWindow

from .calibration import CalibrationProfile
from .estimators import motion_score
from .signal_config import SignalConfig


@dataclass
class MotionResult:
    value: float
    state: str
    confidence: float
    flags: list[str] = field(default_factory=list)


class MotionEstimator:
    """Per-link robust RMS -> empty P99 / walk P95 scale, quality-weighted
    conservative fusion, ~250 ms causal EMA, versioned state thresholds."""

    def __init__(
        self,
        config: SignalConfig,
        profile: CalibrationProfile,
    ) -> None:
        self.config = config
        self.profile = profile
        self._ema: float | None = None

    def reset(self) -> None:
        self._ema = None

    def estimate(self, window: FeatureWindow, quality: float) -> MotionResult:
        fit = self.profile.fit_parameters
        flags: list[str] = []
        if fit is None:
            return MotionResult(0.0, "unknown", 0.0, ["no_fit_parameters"])
        if quality < self.config.unavailable_quality:
            return MotionResult(0.0, "unknown", 0.0, ["insufficient_quality"])

        scores: list[tuple[float, float]] = []
        for feature in window.links.values():
            scores.append(
                (
                    motion_score(feature, fit),
                    feature.valid_carrier_ratio,
                )
            )
        if not scores:
            return MotionResult(0.0, "unknown", 0.0, ["no_frames"])

        weight_sum = sum(weight for _score, weight in scores)
        if weight_sum <= 1e-9:
            fused = sum(score for score, _weight in scores) / len(scores)
        else:
            fused = sum(
                score * weight for score, weight in scores
            ) / weight_sum
        if len(scores) == 1:
            flags.append("single_link")

        if self._ema is None:
            self._ema = fused
        else:
            self._ema = (
                self.config.motion_ema_alpha * fused
                + (1.0 - self.config.motion_ema_alpha) * self._ema
            )
        value = min(1.0, max(0.0, self._ema))

        thresholds = (
            self.config.motion_threshold_idle,
            self.config.motion_threshold_micro,
            self.config.motion_threshold_moving,
        )
        if value < thresholds[0]:
            state = "idle"
        elif value < thresholds[1]:
            state = "micro_motion"
        elif value < thresholds[2]:
            state = "moving"
        else:
            state = "fast_change"
        return MotionResult(
            value=round(value, 6),
            state=state,
            confidence=round(min(1.0, quality), 6),
            flags=flags,
        )
