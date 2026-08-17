"""Depth zone proxy estimator."""

from __future__ import annotations

from dataclasses import dataclass, field

from wifi_contracts import FeatureWindow

from .calibration import CalibrationProfile
from .estimators import depth_bin
from .signal_config import SignalConfig

_ZONE_PROBS = {
    1: (0.75, 0.20, 0.05),
    2: (0.60, 0.30, 0.10),
    3: (0.20, 0.60, 0.20),
    4: (0.10, 0.30, 0.60),
    5: (0.05, 0.20, 0.75),
}
_ZONE_TO_STATE = {1: "near", 2: "near", 3: "mid", 4: "far", 5: "far"}


@dataclass
class DepthResult:
    probabilities: dict[str, float]
    state: str
    confidence: float
    z: float | None = None
    flags: list[str] = field(default_factory=list)


class DepthEstimator:
    """Five-point monotonic zone mapping on dual-link shape asymmetry with
    ~0.8 s causal smoothing. Single RX, insufficient paired coverage,
    topology/calibration mismatch, or OOD always yields unknown."""

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

    def estimate(self, window: FeatureWindow, quality: float) -> DepthResult:
        fit = self.profile.fit_parameters
        flags: list[str] = []
        if fit is None:
            return self._unknown(None, ["no_fit_parameters"])
        if quality < self.config.unavailable_quality:
            return self._unknown(None, ["insufficient_quality"])
        if window.paired is None or len(window.links) < 2:
            return self._unknown(None, ["single_link"])
        if window.paired_packet_coverage < self.config.depth_min_paired_coverage:
            return self._unknown(
                None,
                ["low_paired_coverage"],
            )

        disturbances = window.paired.link_disturbance_scores
        q_a = disturbances.get(sorted(window.links)[0], 0.0)
        q_b = disturbances.get(sorted(window.links)[1], 0.0)
        z = (q_a - q_b) / (q_a + q_b + 1e-9)

        score = window.paired.amplitude_shape_asymmetry
        if self._ema is None:
            self._ema = score
        else:
            self._ema = (
                self.config.depth_ema_alpha * score
                + (1.0 - self.config.depth_ema_alpha) * self._ema
            )
        smoothed = min(1.0, max(0.0, self._ema))
        zone = depth_bin(smoothed, fit)
        if zone is None:
            return self._unknown(z, ["no_depth_boundaries"])

        confidence = min(1.0, quality)
        p_unknown = 1.0 - confidence
        near, mid, far = _ZONE_PROBS[zone]
        scale = 1.0 - p_unknown
        near_r = round(near * scale, 6)
        mid_r = round(mid * scale, 6)
        far_r = round(far * scale, 6)
        probabilities = {
            "near": near_r,
            "mid": mid_r,
            "far": far_r,
            "unknown": round(1.0 - (near_r + mid_r + far_r), 6),
        }
        return DepthResult(
            probabilities=probabilities,
            state=_ZONE_TO_STATE[zone],
            confidence=round(confidence, 6),
            z=round(z, 6),
            flags=flags,
        )

    def _unknown(
        self,
        z: float | None,
        flags: list[str],
    ) -> DepthResult:
        return DepthResult(
            probabilities={"near": 0.0, "mid": 0.0, "far": 0.0, "unknown": 1.0},
            state="unknown",
            confidence=0.0,
            z=z,
            flags=flags,
        )
