"""Performance bound: 2 x 100 pps synthetic stream through the pipeline."""

from __future__ import annotations

import asyncio
import time

from wifi_collector.mock_source import MockFrameSource
from wifi_sensing.calibration import demo_profile
from wifi_sensing.config import FeatureConfig
from wifi_sensing.pipeline import FeaturePipeline


def test_two_link_100pps_stream_within_budget() -> None:
    async def run() -> tuple[int, int, float]:
        source = MockFrameSource(
            scenario="walk_through",
            seed=11,
            rate_hz=100,
            duration_s=30.0,
            real_time=False,
        )
        manifest = await source.open()
        config = FeatureConfig()
        profile = demo_profile(config, manifest.topology_hash)
        pipeline = FeaturePipeline(config, profile)
        frames = 0
        windows = 0
        t0 = time.perf_counter()
        async for frame in source.frames():
            frames += 1
            windows += sum(1 for _ in pipeline.transform([frame], manifest))
        elapsed = time.perf_counter() - t0
        await source.close()
        return frames, windows, elapsed

    frames, windows, elapsed = asyncio.run(run())
    assert frames == 6000  # 30 s x 100 pps x 2 links
    assert windows > 0
    assert elapsed < 15.0, f"pipeline too slow: {elapsed:.2f}s"
