"""Per-link and window-level feature extraction (deterministic, no ML)."""

from __future__ import annotations

import numpy as np
from wifi_contracts import LinkFeatures, WindowQuality

from .calibration import CalibrationProfile
from .cleaning import CleanedFrame
from .config import FeatureConfig

MAD_TO_SIGMA = 1.4826


def _mad(values: np.ndarray) -> float:
    if values.size == 0:
        return 0.0
    median = float(np.median(values))
    return float(np.median(np.abs(values - median)))


def _pearson(a: np.ndarray, b: np.ndarray) -> float:
    if a.size < 2 or b.size != a.size:
        return 0.0
    centered_a = a - a.mean()
    centered_b = b - b.mean()
    denom = float(np.sqrt(np.dot(centered_a, centered_a) * np.dot(centered_b, centered_b)))
    if denom < 1e-12:
        return 0.0
    return float(np.dot(centered_a, centered_b) / denom)


class LinkFeatureExtractor:
    def __init__(self, config: FeatureConfig) -> None:
        self.config = config

    def extract(
        self,
        frames: list[CleanedFrame],
        profile: CalibrationProfile,
    ) -> LinkFeatures:
        cfg = self.config
        flags: list[str] = []
        if not frames:
            return LinkFeatures(
                packet_coverage=0.0,
                subcarrier_coverage=0.0,
                temporal_diff_rms=0.0,
                spectral_band_energy={},
                shape_correlation_to_baseline=0.0,
                quality_flags=["no_frames"],
            )

        expected = cfg.expected_frames_per_window
        packet_coverage = min(1.0, len(frames) / expected)
        timestamps = np.asarray([frame.ts_ns for frame in frames], dtype=np.int64)
        monotonic = bool(np.all(np.diff(timestamps) >= 0))

        carrier_indices = frames[0].carrier_indices
        matrix = np.vstack([frame.amplitudes for frame in frames])
        if matrix.shape[1] != len(carrier_indices):
            flags.append("carrier_shape_mismatch")
            matrix = matrix[:, : len(carrier_indices)]

        median_per_carrier = np.median(matrix, axis=0)
        mad_per_carrier = np.asarray(
            [
                _mad(matrix[:, position])
                for position in range(matrix.shape[1])
            ],
            dtype=np.float64,
        )

        # Motion signals survive common-mode removal as per-carrier changes,
        # so temporal diff RMS spans frames AND carriers, and robust variance
        # measures dispersion of the per-frame spatial RMS.
        temporal_diffs = np.diff(matrix, axis=0)
        temporal_diff_rms = float(
            np.sqrt(np.mean(np.square(temporal_diffs)))
            if temporal_diffs.size
            else 0.0
        )
        spatial_rms = np.sqrt(np.mean(np.square(matrix), axis=1))
        robust_variance = float((MAD_TO_SIGMA * _mad(spatial_rms)) ** 2)

        # Amplitude anomaly ratio: per-carrier deviations beyond k sigmas.
        anomalies = 0
        total = 0
        for position in range(matrix.shape[1]):
            values = matrix[:, position]
            median = float(np.median(values))
            mad = float(np.median(np.abs(values - median)))
            threshold = cfg.anomaly_sigma * mad if mad > 1e-9 else np.inf
            anomalies += int(np.sum(np.abs(values - median) > threshold))
            total += values.size
        anomaly_ratio = anomalies / total if total else 0.0

        mean_amp = np.mean(matrix, axis=1)
        band_energy, spectral_entropy = self._band_analysis(mean_amp)

        shape_corr = self._baseline_correlation(median_per_carrier, profile)
        if profile.valid_count < cfg.min_valid_carriers:
            flags.append("insufficient_carriers")
        valid_ratio = min(1.0, len(carrier_indices) / max(profile.carrier_count, 1))

        if packet_coverage < cfg.low_packet_coverage_threshold:
            flags.append("low_packet_coverage")
        if not monotonic:
            flags.append("non_monotonic_timestamp")
        if anomaly_ratio > cfg.interference_anomaly_threshold:
            flags.append("interference_high")
        if robust_variance > cfg.interference_variance_threshold:
            flags.append("high_robust_variance")
        if temporal_diff_rms > 4.0:
            flags.append("strong_motion")

        return LinkFeatures(
            packet_coverage=round(packet_coverage, 6),
            subcarrier_coverage=round(valid_ratio, 6),
            amplitude_median=[round(float(v), 6) for v in median_per_carrier],
            amplitude_mad=[round(float(v), 6) for v in mad_per_carrier],
            temporal_diff_rms=round(temporal_diff_rms, 6),
            spectral_band_energy={
                name: round(float(value), 6) for name, value in band_energy.items()
            },
            shape_correlation_to_baseline=round(float(max(0.0, shape_corr)), 6),
            quality_flags=flags,
            robust_variance=round(robust_variance, 6),
            amplitude_anomaly_ratio=round(anomaly_ratio, 6),
            spectral_entropy=round(spectral_entropy, 6),
            valid_carrier_ratio=round(valid_ratio, 6),
        )

    def _band_analysis(
        self,
        mean_amp: np.ndarray,
    ) -> tuple[dict[str, float], float]:
        cfg = self.config
        if mean_amp.size < 4:
            return {name: 0.0 for name in cfg.band_edges_hz}, 0.0
        detrended = mean_amp - mean_amp.mean()
        spectrum = np.abs(np.fft.rfft(detrended)) ** 2
        freqs = np.fft.rfftfreq(detrended.size, d=1.0 / cfg.expected_rate_hz)
        total = float(spectrum.sum())
        energies: dict[str, float] = {}
        for name, (low, high) in cfg.band_edges_hz.items():
            mask = (freqs >= low) & (freqs < high)
            energies[name] = float(spectrum[mask].sum()) / total if total > 1e-12 else 0.0
        normalized = np.asarray(
            [max(0.0, min(1.0, value)) for value in energies.values()],
            dtype=np.float64,
        )
        if normalized.size <= 1:
            return energies, 0.0
        normalized = normalized / max(float(normalized.sum()), 1e-12)
        entropy = -float(np.sum(normalized * np.log2(normalized + 1e-12)))
        entropy = entropy / np.log2(normalized.size)
        return energies, float(min(1.0, max(0.0, entropy)))

    def _baseline_correlation(
        self,
        median_per_carrier: np.ndarray,
        profile: CalibrationProfile,
    ) -> float:
        profile_medians = np.asarray(profile.amplitude_median_db, dtype=np.float64)
        profile_valid = np.asarray(profile.valid_carriers, dtype=bool)
        usable = np.where(profile_valid)[0]
        if usable.size == 0:
            return 0.0
        a = median_per_carrier[: usable.size]
        b = profile_medians[usable]
        return _pearson(a, b)


def build_window_quality(
    link_features: dict[str, LinkFeatures],
    *,
    monotonic: bool,
    calibration_match: bool,
    config: FeatureConfig,
) -> WindowQuality:
    anomaly = max(
        (feature.amplitude_anomaly_ratio for feature in link_features.values()),
        default=0.0,
    )
    variance = max(
        (feature.robust_variance for feature in link_features.values()),
        default=0.0,
    )
    interference_score = min(
        1.0,
        0.5 * anomaly / max(config.interference_anomaly_threshold, 1e-9)
        + 0.5 * variance / max(config.interference_variance_threshold, 1e-9),
    )
    ood_flags: list[str] = []
    for feature in link_features.values():
        for flag in ("interference_high", "high_robust_variance", "no_frames"):
            if flag in feature.quality_flags and flag not in ood_flags:
                ood_flags.append(flag)
    if not calibration_match:
        ood_flags.append("calibration_mismatch")
    return WindowQuality(
        timestamp_monotonic=monotonic,
        calibration_match=calibration_match,
        interference_score=round(interference_score, 6),
        ood_flags=ood_flags,
    )
