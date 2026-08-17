"""Calibration profiles: fit (empty-room baseline) and deterministic demo."""

from __future__ import annotations

import hashlib
import json
import math
from datetime import UTC, datetime
from typing import Any, Literal

import numpy as np
from pydantic import BaseModel, ConfigDict, Field, model_validator

from .cleaning import CleanedFrame
from .config import FeatureConfig
from .subcarriers import carrier_indices


class ExpiryRules(BaseModel):
    """Conditions that invalidate a calibration profile."""

    model_config = ConfigDict(extra="forbid")

    max_age_days: int = Field(default=14, ge=1)
    max_temperature_delta_c: float = Field(default=10.0, ge=0.0)
    require_same_topology: bool = True
    require_same_firmware: bool = True
    require_same_feature_version: bool = True
    require_same_channel: bool = True
    require_same_bandwidth: bool = True


class FitParameters(BaseModel):
    """Baseline mappings fitted from train+validation trials."""

    model_config = ConfigDict(extra="forbid")

    motion_empty_p99_db: float = 0.0
    motion_walk_p95_db: float = 1.0
    motion_scale: float = 1.0
    occupancy_anomaly_baseline: float = 0.0
    occupancy_decorrelation_baseline: float = 0.0
    occupancy_thresholds: dict[str, float] = Field(default_factory=dict)
    depth_zone_boundaries: list[float] = Field(default_factory=list)
    depth_single_rx_unknown: bool = True


class CalibrationMetrics(BaseModel):
    """One-shot held-out evaluation; never used to tune fit parameters."""

    model_config = ConfigDict(extra="forbid")

    motion_separation: float = 0.0
    occupancy_ordinal_accuracy: float = 0.0
    depth_monotonic_accuracy: float = 0.0
    held_out_trial_ids: list[str] = Field(default_factory=list)
    evaluated_at: datetime
    simulated: bool


class CalibrationProfile(BaseModel):
    """Per-carrier empty-room baseline plus fit parameters; signed."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["calibration-profile.v1"] = "calibration-profile.v1"
    profile_id: str = Field(min_length=1)
    feature_version: str = Field(min_length=1)
    topology_hash: str = Field(min_length=1)
    bandwidth_mhz: Literal[20, 40]
    carrier_indices: list[int]
    amplitude_median_db: list[float]
    amplitude_mad_db: list[float]
    valid_carriers: list[bool]
    fitted_at: datetime
    source: Literal["recorded", "demo"]
    # Phase 05 additions (additive; older profiles still parse).
    room_id: str = Field(default="demo_room_v1", min_length=1)
    board_hashes: dict[str, str] = Field(default_factory=dict)
    positions: dict[str, str] = Field(default_factory=dict)
    channel: int = Field(default=6, ge=1, le=196)
    firmware_version: str = Field(default="wifi-spatial-council-fw/0.1.0")
    estimator_version: str = Field(default="estimator-v1")
    environment: str | None = None
    fit_parameters: FitParameters | None = None
    training_trial_ids: list[str] = Field(default_factory=list)
    validation_trial_ids: list[str] = Field(default_factory=list)
    metrics: CalibrationMetrics | None = None
    expiry: ExpiryRules = Field(default_factory=ExpiryRules)
    checksum: str = Field(default="", pattern=r"^(sha256:[0-9a-f]{64})?$")
    simulated: bool = False
    state: Literal["active", "failed"] = "active"

    @model_validator(mode="after")
    def _demo_must_be_simulated(self) -> CalibrationProfile:
        if self.source == "demo" and not self.simulated:
            raise ValueError("demo profiles must carry simulated=true")
        return self

    @property
    def carrier_count(self) -> int:
        return len(self.carrier_indices)

    @property
    def valid_count(self) -> int:
        return sum(self.valid_carriers)

    def canonical_payload(self) -> str:
        data = self.model_dump(mode="json", exclude={"checksum"})
        return json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False)

    def compute_checksum(self) -> str:
        return "sha256:" + hashlib.sha256(
            self.canonical_payload().encode("utf-8")
        ).hexdigest()

    def verify_integrity(self) -> bool:
        return self.checksum == self.compute_checksum()

    @classmethod
    def create(cls, **values: Any) -> CalibrationProfile:
        """Construct a profile with its checksum computed from the payload."""
        values.setdefault("schema_version", "calibration-profile.v1")
        profile = cls(**values)
        profile.checksum = profile.compute_checksum()
        return profile


def profile_match_score(
    profile: CalibrationProfile,
    *,
    topology_hash: str,
    channel: int,
    bandwidth_mhz: int,
    firmware_version: str,
    feature_version: str,
) -> tuple[float, list[str]]:
    """Match score in [0, 1] plus the list of mismatched attributes."""
    checks = {
        "topology": profile.topology_hash == topology_hash,
        "channel": profile.channel == channel,
        "bandwidth": profile.bandwidth_mhz == bandwidth_mhz,
        "firmware": profile.firmware_version == firmware_version,
        "feature_version": profile.feature_version == feature_version,
    }
    mismatches = [name for name, ok in checks.items() if not ok]
    score = (len(checks) - len(mismatches)) / len(checks)
    return score, mismatches


def hard_invalidation_reasons(
    profile: CalibrationProfile,
    *,
    topology_hash: str,
    channel: int,
    bandwidth_mhz: int,
    firmware_version: str,
    feature_version: str,
) -> list[str]:
    """Attributes whose change invalidates the profile per expiry rules."""
    _score, mismatches = profile_match_score(
        profile,
        topology_hash=topology_hash,
        channel=channel,
        bandwidth_mhz=bandwidth_mhz,
        firmware_version=firmware_version,
        feature_version=feature_version,
    )
    rules = profile.expiry
    hard: list[str] = []
    if "topology" in mismatches and rules.require_same_topology:
        hard.append("topology")
    if "channel" in mismatches and rules.require_same_channel:
        hard.append("channel")
    if "bandwidth" in mismatches and rules.require_same_bandwidth:
        hard.append("bandwidth")
    if "firmware" in mismatches and rules.require_same_firmware:
        hard.append("firmware")
    if "feature_version" in mismatches and rules.require_same_feature_version:
        hard.append("feature_version")
    return hard


def fit_profile(
    frames: list[CleanedFrame],
    config: FeatureConfig,
    *,
    profile_id: str,
    topology_hash: str,
) -> CalibrationProfile:
    """Fit an empty-room baseline from cleaned frames (deterministic)."""
    if not frames:
        raise ValueError("cannot fit a profile without frames")
    carrier_indices_list = frames[0].carrier_indices
    matrix = np.vstack([frame.amplitudes for frame in frames])
    median_per_carrier = np.median(matrix, axis=0)
    mad_per_carrier = np.asarray(
        [
            float(np.median(np.abs(matrix[:, i] - np.median(matrix[:, i]))))
            for i in range(matrix.shape[1])
        ],
        dtype=np.float64,
    )
    # Drop the most unstable carriers (highest MAD), at most the configured
    # fraction. If fewer than min_valid_carriers survive, the profile is
    # still returned with fewer valid carriers; the pipeline flags it.
    order = np.argsort(-mad_per_carrier)
    drop_count = min(
        len(carrier_indices_list) - config.min_valid_carriers,
        round(config.drop_unstable_frac * len(carrier_indices_list)),
    )
    drop_count = max(0, drop_count)
    valid = np.ones(len(carrier_indices_list), dtype=bool)
    valid[order[:drop_count]] = False
    return CalibrationProfile.create(
        schema_version="calibration-profile.v1",
        profile_id=profile_id,
        feature_version=config.feature_version,
        topology_hash=topology_hash,
        channel=config.expected_channel,
        bandwidth_mhz=config.expected_bandwidth_mhz,
        carrier_indices=carrier_indices_list,
        amplitude_median_db=[round(float(v), 6) for v in median_per_carrier],
        amplitude_mad_db=[round(float(v), 6) for v in mad_per_carrier],
        valid_carriers=[bool(v) for v in valid],
        fitted_at=datetime.now(UTC),
        source="recorded",
        simulated=False,
        state="active",
    )


def demo_profile(
    config: FeatureConfig,
    topology_hash: str,
    *,
    profile_id: str = "demo_room_v1",
    carrier_count: int = 64,
) -> CalibrationProfile:
    """Deterministic demo baseline + fit parameters for replay/mock.

    The fit parameters below are DEMO constants derived from the simulated
    calibration (motion P99/P95, occupancy thresholds, depth boundaries).
    They are not hardware evidence and are clearly marked simulated.
    """
    indices = carrier_indices(carrier_count * 2, config.expected_bandwidth_mhz)
    medians = [42.0 + 5.0 * math.sin(index / 6.0) for index in indices]
    mads = [0.3 + 0.05 * abs(index) for index in indices]
    return CalibrationProfile.create(
        schema_version="calibration-profile.v1",
        profile_id=profile_id,
        feature_version=config.feature_version,
        topology_hash=topology_hash,
        room_id=profile_id,
        board_hashes={
            "tx": "sha256:" + "0" * 64,
            "rx-a": "sha256:" + "1" * 64,
            "rx-b": "sha256:" + "2" * 64,
        },
        positions={
            "rx-a": "corner A, h=1.2m",
            "rx-b": "corner B, h=1.2m",
        },
        channel=config.expected_channel,
        bandwidth_mhz=config.expected_bandwidth_mhz,
        carrier_indices=indices,
        amplitude_median_db=[round(v, 6) for v in medians],
        amplitude_mad_db=[round(v, 6) for v in mads],
        valid_carriers=[True] * len(indices),
        fitted_at=datetime(2026, 8, 6, tzinfo=UTC),
        source="demo",
        simulated=True,
        fit_parameters=FitParameters(
            motion_empty_p99_db=0.075653,
            motion_walk_p95_db=1.030157,
            motion_scale=1.047664,
            occupancy_anomaly_baseline=0.03543,
            occupancy_decorrelation_baseline=0.015188,
            occupancy_thresholds={"low_medium": 0.176677, "medium_high": 0.320864},
            depth_zone_boundaries=[0.08202, 0.289828, 0.500128, 0.634637],
            depth_single_rx_unknown=True,
        ),
        state="active",
    )
