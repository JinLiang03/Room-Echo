"""Feature extraction scenarios: noise, motion, gain, spike, loss, single-RX."""

from __future__ import annotations

import asyncio

from wifi_collector.mock_source import MockFrameSource
from wifi_sensing.calibration import demo_profile
from wifi_sensing.config import FeatureConfig
from wifi_sensing.pipeline import FeaturePipeline


async def _windows(scenario: str, seed: int = 3, duration: float = 5.0):
    source = MockFrameSource(
        scenario=scenario,
        seed=seed,
        rate_hz=100,
        duration_s=duration,
        real_time=False,
    )
    manifest = await source.open()
    config = FeatureConfig()
    profile = demo_profile(config, manifest.topology_hash)
    pipeline = FeaturePipeline(config, profile)
    windows = []
    async for frame in source.frames():
        windows.extend(pipeline.transform([frame], manifest))
    await source.close()
    return windows


def test_empty_room_noise_is_quiet() -> None:
    windows = asyncio.run(_windows("idle"))
    assert windows
    for window in windows:
        for feature in window.links.values():
            assert feature.temporal_diff_rms < 0.2
            assert feature.amplitude_anomaly_ratio < 0.1
            assert feature.robust_variance < 1.0
            assert "interference_high" not in feature.quality_flags


def test_walk_has_higher_motion_features_than_idle() -> None:
    idle = asyncio.run(_windows("idle", duration=5.0))
    walk = asyncio.run(_windows("walk_through", duration=5.0))
    idle_rms = max(f.temporal_diff_rms for w in idle for f in w.links.values())
    walk_rms = max(f.temporal_diff_rms for w in walk for f in w.links.values())
    assert walk_rms > idle_rms
    assert walk_rms > 0.05


def test_packet_loss_flags_low_coverage() -> None:
    windows = asyncio.run(_windows("packet_loss", duration=5.0))
    assert any(
        "low_packet_coverage" in feature.quality_flags
        for window in windows
        for feature in window.links.values()
    )


def test_single_link_does_not_fabricate_paired_features() -> None:
    async def run() -> None:
        source = MockFrameSource(
            scenario="idle",
            seed=1,
            rate_hz=100,
            duration_s=5.0,
            real_time=False,
        )
        manifest = await source.open()
        config = FeatureConfig()
        profile = demo_profile(config, manifest.topology_hash)
        pipeline = FeaturePipeline(config, profile)
        windows = []
        async for frame in source.frames():
            if frame.link_id == "rx-b":
                continue  # single RX only
            windows.extend(pipeline.transform([frame], manifest))
        await source.close()
        assert windows
        for window in windows:
            assert window.paired is None
            assert window.paired_packet_coverage == 0.0
            assert "single_link" in window.quality.ood_flags

    asyncio.run(run())


def test_windows_carry_versioned_metadata() -> None:
    windows = asyncio.run(_windows("idle", duration=3.0))
    window = windows[0]
    assert window.feature_version == "features-v2"
    assert window.quality is not None
    assert window.paired is not None
    assert window.stride_ms == 250
