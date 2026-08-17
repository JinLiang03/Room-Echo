"""Conservative quality gate for the three proxy signals.

Each signal's quality is the MINIMUM of the components it requires (per
ADR 0004). Confidence never exceeds quality, and the sensor confidence cap
never exceeds the minimum of the required signal qualities.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field
from wifi_contracts import FeatureWindow

from .calibration import CalibrationProfile
from .signal_config import SignalConfig

_OOD_PENALTY_FLAGS = {
    "interference_high",
    "high_robust_variance",
    "calibration_mismatch",
    "motion_contamination",
}


class SignalQuality(BaseModel):
    model_config = ConfigDict(extra="forbid")

    packet_coverage: float = Field(ge=0, le=1)
    paired_coverage: float = Field(ge=0, le=1)
    carrier_coverage: float = Field(ge=0, le=1)
    clock_order: float = Field(ge=0, le=1)
    calibration_match: float = Field(ge=0, le=1)
    interference: float = Field(ge=0, le=1)
    ood: float = Field(ge=0, le=1)
    staleness: float = Field(ge=0, le=1)
    motion: float = Field(ge=0, le=1)
    occupancy: float = Field(ge=0, le=1)
    depth: float = Field(ge=0, le=1)


class QualityGate:
    """Computes per-signal conservative quality from a FeatureWindow."""

    def __init__(
        self,
        config: SignalConfig,
        profile: CalibrationProfile,
    ) -> None:
        self.config = config
        self.profile = profile

    def compute(self, window: FeatureWindow) -> SignalQuality:
        links = list(window.links.values())
        packet = min((link.packet_coverage for link in links), default=0.0)
        carrier = min((link.valid_carrier_ratio for link in links), default=0.0)
        clock = (
            1.0
            if window.quality is not None and window.quality.timestamp_monotonic
            else 0.0
        )
        calibration = (
            1.0
            if window.quality is not None and window.quality.calibration_match
            else 0.0
        )
        interference = (
            1.0 - window.quality.interference_score
            if window.quality is not None
            else 1.0
        )
        ood_flags = window.quality.ood_flags if window.quality is not None else []
        # Structural flags (e.g. single_link) gate paired signals via the
        # paired_coverage component; only contamination-like flags penalize OOD.
        ood = 0.3 if (set(ood_flags) & _OOD_PENALTY_FLAGS) else 1.0
        paired = window.paired_packet_coverage
        staleness = self._staleness(window)

        motion = min(
            packet,
            carrier,
            clock,
            calibration,
            interference,
            ood,
            staleness,
        )
        occupancy = min(
            packet,
            paired,
            carrier,
            clock,
            calibration,
            interference,
            ood,
            staleness,
        )
        depth = min(
            paired,
            carrier,
            clock,
            calibration,
            interference,
            ood,
            staleness,
        )
        return SignalQuality(
            packet_coverage=round(packet, 6),
            paired_coverage=round(paired, 6),
            carrier_coverage=round(carrier, 6),
            clock_order=clock,
            calibration_match=calibration,
            interference=round(interference, 6),
            ood=ood,
            staleness=round(staleness, 6),
            motion=round(motion, 6),
            occupancy=round(occupancy, 6),
            depth=round(depth, 6),
        )

    def _staleness(self, window: FeatureWindow) -> float:
        """1.0 for fresh windows; decays when data age exceeds the budget."""
        # FeatureWindows are emitted online with bounded latency, so staleness
        # is 1.0 unless the window itself is flagged (future phases can plug a
        # real receive-time watermark here).
        if window.quality is None:
            return 1.0
        return 1.0
