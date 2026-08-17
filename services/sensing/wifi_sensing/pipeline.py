"""FeaturePipeline: frames in -> FeatureWindow out (online, deterministic)."""

from __future__ import annotations

from collections.abc import Iterable, Iterator

from wifi_contracts import FeatureWindow, NormalizedCsiFrame, SourceManifest

from .calibration import CalibrationProfile
from .cleaning import CleaningTransformer
from .config import FeatureConfig
from .features import LinkFeatureExtractor, build_window_quality
from .paired import PairedFeatureExtractor
from .windows import SlidingWindowBuffer, Window


class FeaturePipeline:
    def __init__(
        self,
        config: FeatureConfig,
        profile: CalibrationProfile,
    ) -> None:
        self.config = config
        self.profile = profile
        self._cleaner = CleaningTransformer(config)
        self._buffer = SlidingWindowBuffer(config)
        self._link_extractor = LinkFeatureExtractor(config)
        self._paired_extractor = PairedFeatureExtractor(config)

    def reset(self) -> None:
        self._cleaner.reset()
        self._buffer.reset()

    def transform(
        self,
        frames: Iterable[NormalizedCsiFrame],
        manifest: SourceManifest,
    ) -> Iterator[FeatureWindow]:
        for frame in frames:
            cleaned = self._cleaner.clean(frame, manifest)
            if cleaned is None:
                continue
            for window in self._buffer.push(cleaned):
                yield self._emit(window, manifest)

    def flush(
        self,
        manifest: SourceManifest,
    ) -> Iterator[FeatureWindow]:
        for window in self._buffer.flush():
            yield self._emit(window, manifest)

    def _emit(
        self,
        window: Window,
        manifest: SourceManifest,
    ) -> FeatureWindow:
        features = {
            link_id: self._link_extractor.extract(frames, self.profile)
            for link_id, frames in window.frames.items()
            if frames
        }
        monotonic = all(
            feature.quality_flags.count("non_monotonic_timestamp") == 0
            for feature in features.values()
        )
        calibration_match = self.profile.topology_hash == manifest.topology_hash
        paired, paired_coverage = self._paired_extractor.extract(window, features)
        quality = build_window_quality(
            features,
            monotonic=monotonic,
            calibration_match=calibration_match,
            config=self.config,
        )
        if paired is None and len(features) < 2:
            quality.ood_flags.append("single_link")
        return FeatureWindow(
            schema_version="1.0.0",
            session_id=manifest.session_id,
            window_id=f"window-{window.start_ns}",
            source_mode=manifest.source_mode,
            start_ns=window.start_ns,
            end_ns=window.end_ns,
            stride_ms=self.config.stride_ms,
            topology_hash=self.profile.topology_hash,
            calibration_profile_id=self.profile.profile_id,
            links=features,
            paired_packet_coverage=paired_coverage,
            feature_version=self.config.feature_version,
            quality=quality,
            paired=paired,
        )
