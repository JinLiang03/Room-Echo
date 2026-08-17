"""Feature windows and the three calibrated proxy signals."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .base import (
    HASH_PATTERN,
    PROBABILITY_TOLERANCE,
    SCHEMA_BASE,
    SourceMode,
    require_probability_sum,
)


class LinkFeatures(BaseModel):
    """Per-link feature summaries; arrays never enter agent input."""

    model_config = ConfigDict(extra="forbid")

    packet_coverage: float = Field(ge=0, le=1)
    subcarrier_coverage: float = Field(ge=0, le=1)
    amplitude_median: list[float] = Field(default_factory=list)
    amplitude_mad: list[float] = Field(default_factory=list)
    temporal_diff_rms: float = Field(ge=0)
    spectral_band_energy: dict[str, float] = Field(default_factory=dict)
    shape_correlation_to_baseline: float = Field(ge=0, le=1)
    quality_flags: list[str] = Field(default_factory=list)
    # Phase 04 additions (additive patch; older readers still parse).
    robust_variance: float = Field(default=0.0, ge=0)
    amplitude_anomaly_ratio: float = Field(default=0.0, ge=0, le=1)
    spectral_entropy: float = Field(default=0.0, ge=0, le=1)
    valid_carrier_ratio: float = Field(default=1.0, ge=0, le=1)


class WindowQuality(BaseModel):
    """Window-level measurement quality; never inflated by agents."""

    model_config = ConfigDict(extra="forbid")

    timestamp_monotonic: bool = True
    calibration_match: bool = True
    interference_score: float = Field(default=0.0, ge=0, le=1)
    ood_flags: list[str] = Field(default_factory=list)


class PairedFeatures(BaseModel):
    """Dual-link features; never derived from cross-RX raw phase."""

    model_config = ConfigDict(extra="forbid")

    link_disturbance_scores: dict[str, float] = Field(default_factory=dict)
    amplitude_shape_asymmetry: float = Field(default=0.0, ge=0, le=1)


class FeatureWindow(BaseModel):
    """A sliding window of per-link features, recomputable from raw frames."""

    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "$id": f"{SCHEMA_BASE}/feature_window.schema.json",
            "title": "FeatureWindow",
        },
    )

    schema_version: Literal["1.0.0"] = "1.0.0"
    session_id: str = Field(min_length=1)
    window_id: str = Field(min_length=1)
    source_mode: SourceMode
    start_ns: int = Field(ge=0)
    end_ns: int = Field(ge=0)
    stride_ms: int = Field(ge=1)
    topology_hash: str = Field(pattern=HASH_PATTERN)
    calibration_profile_id: str = Field(min_length=1)
    links: dict[str, LinkFeatures] = Field(min_length=1)
    paired_packet_coverage: float = Field(ge=0, le=1)
    feature_version: str = Field(min_length=1)
    quality: WindowQuality | None = None
    paired: PairedFeatures | None = None

    @model_validator(mode="after")
    def _window_order(self) -> FeatureWindow:
        if self.end_ns < self.start_ns:
            raise ValueError("end_ns must be >= start_ns")
        return self


MotionState = Literal["idle", "micro_motion", "moving", "fast_change", "unknown"]
OccupancyState = Literal["low", "medium", "high", "unknown"]
DepthState = Literal["near", "mid", "far", "unknown"]
SignalStatus = Literal["ok", "degraded", "insufficient_signal", "uncalibrated"]


class MotionSignal(BaseModel):
    model_config = ConfigDict(extra="forbid")

    value: float = Field(ge=0, le=1)
    state: MotionState
    confidence: float = Field(ge=0, le=1)


class OccupancyProbabilities(BaseModel):
    model_config = ConfigDict(extra="forbid")

    low: float = Field(ge=0, le=1)
    medium: float = Field(ge=0, le=1)
    high: float = Field(ge=0, le=1)
    unknown: float = Field(ge=0, le=1)

    @model_validator(mode="after")
    def _sums_to_one(self) -> OccupancyProbabilities:
        require_probability_sum([self.low, self.medium, self.high, self.unknown])
        return self


class OccupancyDensity(BaseModel):
    """Occupancy/obstruction density proxy — not a person count."""

    model_config = ConfigDict(extra="forbid")

    probabilities: OccupancyProbabilities
    state: OccupancyState
    confidence: float = Field(ge=0, le=1)

    @model_validator(mode="after")
    def _unknown_state_rule(self) -> OccupancyDensity:
        if self.state == "unknown" and not (
            abs(self.probabilities.unknown - 1.0) <= PROBABILITY_TOLERANCE
        ):
            raise ValueError("unknown state requires unknown probability == 1")
        return self


class DepthProbabilities(BaseModel):
    model_config = ConfigDict(extra="forbid")

    near: float = Field(ge=0, le=1)
    mid: float = Field(ge=0, le=1)
    far: float = Field(ge=0, le=1)
    unknown: float = Field(ge=0, le=1)

    @model_validator(mode="after")
    def _sums_to_one(self) -> DepthProbabilities:
        require_probability_sum([self.near, self.mid, self.far, self.unknown])
        return self


class DepthZone(BaseModel):
    """Propagation depth proxy — not metric distance."""

    model_config = ConfigDict(extra="forbid")

    probabilities: DepthProbabilities
    state: DepthState
    confidence: float = Field(ge=0, le=1)

    @model_validator(mode="after")
    def _unknown_state_rule(self) -> DepthZone:
        if self.state == "unknown" and not (
            abs(self.probabilities.unknown - 1.0) <= PROBABILITY_TOLERANCE
        ):
            raise ValueError("unknown state requires unknown probability == 1")
        return self


class SignalTriplet(BaseModel):
    """The three calibrated proxies plus the sensor confidence cap."""

    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "$id": f"{SCHEMA_BASE}/signal_triplet.schema.json",
            "title": "SignalTriplet",
        },
    )

    schema_version: Literal["1.0.0"]
    session_id: str = Field(min_length=1)
    window_id: str = Field(min_length=1)
    source_mode: SourceMode
    started_at: datetime
    ended_at: datetime
    motion: MotionSignal
    occupancy_density: OccupancyDensity
    depth_zone: DepthZone
    sensor_confidence_cap: float = Field(ge=0, le=1)
    evidence_refs: list[str]
    status: SignalStatus

    @model_validator(mode="after")
    def _triplet_invariants(self) -> SignalTriplet:
        if self.ended_at < self.started_at:
            raise ValueError("ended_at must be >= started_at")
        cap = self.sensor_confidence_cap
        for label, confidence in (
            ("motion", self.motion.confidence),
            ("occupancy", self.occupancy_density.confidence),
            ("depth", self.depth_zone.confidence),
        ):
            if confidence > cap:
                raise ValueError(
                    f"{label}.confidence ({confidence}) must not exceed "
                    f"sensor_confidence_cap ({cap})"
                )
        return self
