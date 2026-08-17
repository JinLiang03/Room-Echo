"""SignalEstimator: FeatureWindow -> SignalTriplet with quality invariants."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal, cast

from wifi_contracts import (
    DepthProbabilities,
    DepthZone,
    FeatureWindow,
    MotionSignal,
    OccupancyDensity,
    OccupancyProbabilities,
    SignalTriplet,
    SourceMode,
)

from .calibration import CalibrationProfile
from .signal_config import SignalConfig
from .signal_depth import DepthEstimator
from .signal_gate import QualityGate
from .signal_motion import MotionEstimator
from .signal_occupancy import OccupancyEstimator


def _dt_from_ns(ns: int) -> datetime:
    return datetime.fromtimestamp(ns / 1_000_000_000, tz=UTC)


class SignalEstimator:
    """Deterministic three-signal estimator; never touches agent outputs."""

    def __init__(
        self,
        config: SignalConfig,
        profile: CalibrationProfile,
    ) -> None:
        self.config = config
        self.profile = profile
        self.gate = QualityGate(config, profile)
        self.motion = MotionEstimator(config, profile)
        self.occupancy = OccupancyEstimator(config, profile)
        self.depth = DepthEstimator(config, profile)

    def reset(self) -> None:
        self.motion.reset()
        self.depth.reset()

    def estimate(self, window: FeatureWindow) -> SignalTriplet:
        quality = self.gate.compute(window)
        motion = self.motion.estimate(window, quality.motion)
        occupancy = self.occupancy.estimate(
            window,
            quality.occupancy,
            motion.value if motion.state != "unknown" else None,
        )
        depth = self.depth.estimate(window, quality.depth)

        cap = round(min(quality.motion, quality.occupancy, quality.depth), 6)
        motion_confidence = round(min(motion.confidence, cap), 6)
        occupancy_confidence = round(min(occupancy.confidence, cap), 6)
        depth_confidence = round(min(depth.confidence, cap), 6)

        status = self._status(
            motion.state,
            occupancy.state,
            depth.state,
            quality.calibration_match,
            min(motion_confidence, occupancy_confidence, depth_confidence),
        )
        triplet = SignalTriplet(
            schema_version="1.0.0",
            session_id=window.session_id,
            window_id=window.window_id,
            source_mode=window.source_mode,
            started_at=_dt_from_ns(window.start_ns),
            ended_at=_dt_from_ns(window.end_ns),
            motion=MotionSignal(
                value=motion.value,
                state=cast(
                    Literal[
                        "idle",
                        "micro_motion",
                        "moving",
                        "fast_change",
                        "unknown",
                    ],
                    motion.state,
                ),
                confidence=motion_confidence,
            ),
            occupancy_density=OccupancyDensity(
                probabilities=OccupancyProbabilities(
                    low=occupancy.probabilities["low"],
                    medium=occupancy.probabilities["medium"],
                    high=occupancy.probabilities["high"],
                    unknown=occupancy.probabilities["unknown"],
                ),
                state=cast(
                    Literal["low", "medium", "high", "unknown"],
                    occupancy.state,
                ),
                confidence=occupancy_confidence,
            ),
            depth_zone=DepthZone(
                probabilities=DepthProbabilities(
                    near=depth.probabilities["near"],
                    mid=depth.probabilities["mid"],
                    far=depth.probabilities["far"],
                    unknown=depth.probabilities["unknown"],
                ),
                state=cast(Literal["near", "mid", "far", "unknown"], depth.state),
                confidence=depth_confidence,
            ),
            sensor_confidence_cap=cap,
            evidence_refs=[],
            status=cast(
                Literal["ok", "degraded", "insufficient_signal", "uncalibrated"],
                status,
            ),
        )
        return triplet

    def estimate_stale(
        self,
        *,
        session_id: str,
        source_mode: SourceMode,
        window_id: str = "stale",
    ) -> SignalTriplet:
        """Clear any previous valid state; unknown, zero confidence."""
        now = datetime.now(UTC)
        self.reset()
        return SignalTriplet(
            schema_version="1.0.0",
            session_id=session_id,
            window_id=window_id,
            source_mode=source_mode,
            started_at=now,
            ended_at=now,
            motion=MotionSignal(value=0.0, state="unknown", confidence=0.0),
            occupancy_density=OccupancyDensity(
                probabilities=OccupancyProbabilities(
                    low=0.0,
                    medium=0.0,
                    high=0.0,
                    unknown=1.0,
                ),
                state="unknown",
                confidence=0.0,
            ),
            depth_zone=DepthZone(
                probabilities=DepthProbabilities(
                    near=0.0,
                    mid=0.0,
                    far=0.0,
                    unknown=1.0,
                ),
                state="unknown",
                confidence=0.0,
            ),
            sensor_confidence_cap=0.0,
            evidence_refs=[],
            status="insufficient_signal",
        )

    def _status(
        self,
        motion_state: str,
        occupancy_state: str,
        depth_state: str,
        calibration_match: float,
        min_confidence: float,
    ) -> str:
        if calibration_match < 1.0:
            return "uncalibrated"
        unknown_count = sum(
            state == "unknown"
            for state in (motion_state, occupancy_state, depth_state)
        )
        if unknown_count >= 2 or min_confidence < self.config.unavailable_quality:
            return "insufficient_signal"
        if min_confidence < self.config.degraded_quality:
            return "degraded"
        return "ok"
