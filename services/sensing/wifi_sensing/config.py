"""Feature extraction configuration; every parameter is versioned."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class FeatureConfig(BaseModel):
    """Deterministic parameters for cleaning, windows, and features."""

    model_config = ConfigDict(extra="forbid")

    feature_version: str = Field(default="features-v2", min_length=1)
    window_s: float = Field(default=2.0, ge=0.1, le=30.0)
    stride_ms: int = Field(default=250, ge=10, le=5000)
    expected_rate_hz: float = Field(default=100.0, gt=0, le=1000)
    expected_channel: int = Field(default=6, ge=1, le=196)
    expected_bandwidth_mhz: Literal[20, 40] = 20
    hampel_window: int = Field(default=11, ge=3, le=101)
    hampel_n_sigmas: float = Field(default=3.0, ge=1.0, le=10.0)
    ema_alpha: float = Field(default=0.3, ge=0.01, le=1.0)
    anomaly_sigma: float = Field(default=3.0, ge=1.0, le=10.0)
    band_edges_hz: dict[str, tuple[float, float]] = Field(
        default_factory=lambda: {
            "0-1Hz": (0.0, 1.0),
            "1-4Hz": (1.0, 4.0),
            "4-8Hz": (4.0, 8.0),
        }
    )
    min_valid_carriers: int = Field(default=32, ge=8, le=256)
    drop_unstable_frac: float = Field(default=0.2, ge=0.0, le=0.9)
    mask_dc: bool = True
    guard_carriers: int = Field(default=0, ge=0, le=16)
    low_packet_coverage_threshold: float = Field(default=0.8, ge=0.0, le=1.0)
    max_interframe_gap_ms: float = Field(default=500.0, ge=10.0)
    interference_anomaly_threshold: float = Field(default=0.15, ge=0.0, le=1.0)
    interference_variance_threshold: float = Field(default=4.0, ge=0.0, le=100.0)

    @property
    def window_ns(self) -> int:
        return int(self.window_s * 1_000_000_000)

    @property
    def stride_ns(self) -> int:
        return self.stride_ms * 1_000_000

    @property
    def expected_frames_per_window(self) -> float:
        return self.expected_rate_hz * self.window_s
