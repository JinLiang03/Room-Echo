"""Quality prechecks for recorded calibration trials."""

from __future__ import annotations

from pathlib import Path

from wifi_collector.replay_source import ReplayFrameSource
from wifi_contracts import FeatureWindow

from .calibration import demo_profile
from .config import FeatureConfig
from .pipeline import FeaturePipeline


async def check_trial_quality(
    bundle: Path,
    config: FeatureConfig | None = None,
) -> tuple[bool, list[str]]:
    """Replay a trial and check coverage/carrier gates (for re-record)."""
    config = config or FeatureConfig()
    source = ReplayFrameSource(bundle, real_time=False)
    manifest = await source.open()
    profile = demo_profile(config, manifest.topology_hash)
    pipeline = FeaturePipeline(config, profile)
    windows: list[FeatureWindow] = []
    async for frame in source.frames():
        windows.extend(pipeline.transform([frame], manifest))
    await source.close()

    reasons: list[str] = []
    if not windows:
        reasons.append("no windows extracted")
    for window in windows:
        for feature in window.links.values():
            if feature.packet_coverage < config.low_packet_coverage_threshold:
                reasons.append("low_packet_coverage")
            if feature.valid_carrier_ratio < 0.5:
                reasons.append("insufficient_carriers")
            break
    return not reasons, sorted(set(reasons))
