"""Signal estimator configuration (versioned, deterministic)."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class SignalConfig(BaseModel):
    """Parameters for the three proxy-signal estimators and evidence trigger."""

    model_config = ConfigDict(extra="forbid")

    version: str = Field(default="signals-v1", min_length=1)
    motion_ema_alpha: float = Field(default=0.5, ge=0.01, le=1.0)
    motion_threshold_idle: float = Field(default=0.15, ge=0.0, le=1.0)
    motion_threshold_micro: float = Field(default=0.4, ge=0.0, le=1.0)
    motion_threshold_moving: float = Field(default=0.7, ge=0.0, le=1.0)
    occupancy_motion_freeze: float = Field(default=0.6, ge=0.0, le=1.0)
    occupancy_low_band: str = Field(default="0-1Hz", min_length=1)
    depth_ema_alpha: float = Field(default=0.3, ge=0.01, le=1.0)
    depth_min_paired_coverage: float = Field(default=0.5, ge=0.0, le=1.0)
    unavailable_quality: float = Field(default=0.4, ge=0.0, le=1.0)
    degraded_quality: float = Field(default=0.7, ge=0.0, le=1.0)
    evidence_cooldown_s: float = Field(default=3.0, ge=0.1)
    evidence_stable_change_windows: int = Field(default=3, ge=1)
    max_data_age_s: float = Field(default=5.0, ge=0.1)
