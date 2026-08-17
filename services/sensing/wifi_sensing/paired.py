"""Paired dual-link features; single-link windows never fabricate pairing."""

from __future__ import annotations

import numpy as np
from wifi_contracts import LinkFeatures, PairedFeatures

from .config import FeatureConfig
from .features import _pearson
from .windows import Window


class PairedFeatureExtractor:
    def __init__(self, config: FeatureConfig) -> None:
        self.config = config

    def extract(
        self,
        window: Window,
        features: dict[str, LinkFeatures],
    ) -> tuple[PairedFeatures | None, float]:
        """Return (paired_features, paired_packet_coverage)."""
        if len(features) < 2 or len(window.frames) < 2:
            return None, 0.0

        link_ids = sorted(window.frames)
        a_id, b_id = link_ids[0], link_ids[1]
        a_seqs = {frame.seq for frame in window.frames[a_id]}
        b_seqs = {frame.seq for frame in window.frames[b_id]}
        union = a_seqs | b_seqs
        paired_coverage = len(a_seqs & b_seqs) / len(union) if union else 0.0

        disturbance: dict[str, float] = {}
        for link_id, feature in features.items():
            score = min(
                1.0,
                0.5 * feature.temporal_diff_rms / 1.0
                + 0.5 * feature.amplitude_anomaly_ratio / 0.2,
            )
            disturbance[link_id] = round(score, 6)

        a_median = np.asarray(features[a_id].amplitude_median, dtype=np.float64)
        b_median = np.asarray(features[b_id].amplitude_median, dtype=np.float64)
        correlation = _pearson(a_median, b_median)
        asymmetry = min(1.0, max(0.0, 1.0 - abs(correlation)))

        return (
            PairedFeatures(
                link_disturbance_scores=disturbance,
                amplitude_shape_asymmetry=round(asymmetry, 6),
            ),
            round(paired_coverage, 6),
        )
