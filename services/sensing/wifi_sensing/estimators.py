"""Baseline estimators used by calibration fit/evaluate (Phase 06 formalizes)."""

from __future__ import annotations

from wifi_contracts import LinkFeatures, PairedFeatures

from .calibration import FitParameters


def motion_score(
    features: LinkFeatures,
    fit: FitParameters,
) -> float:
    """Robust scale: empty P99 -> 0, standard walk P95 -> 1, clipped."""
    numerator = features.temporal_diff_rms - fit.motion_empty_p99_db
    return min(1.0, max(0.0, numerator * fit.motion_scale))


def occupancy_score(features: LinkFeatures) -> float:
    """Low-frequency anomaly ratio + shape decorrelation (0..1)."""
    decorrelation = 1.0 - features.shape_correlation_to_baseline
    return 0.5 * features.amplitude_anomaly_ratio + 0.5 * decorrelation


def occupancy_bin(score: float, fit: FitParameters) -> str:
    thresholds = fit.occupancy_thresholds
    if score <= thresholds.get("low_medium", 0.5):
        return "low"
    if score <= thresholds.get("medium_high", 0.8):
        return "medium"
    return "high"


def depth_score(paired: PairedFeatures | None) -> float | None:
    """Dual-link amplitude-shape asymmetry; None when single RX (unknown)."""
    if paired is None:
        return None
    return paired.amplitude_shape_asymmetry


def depth_bin(score: float | None, fit: FitParameters) -> int | None:
    if score is None or not fit.depth_zone_boundaries:
        return None
    boundaries = fit.depth_zone_boundaries
    zone = 1
    for boundary in boundaries:
        if score > boundary:
            zone += 1
    return min(5, zone)
