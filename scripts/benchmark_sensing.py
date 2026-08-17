#!/usr/bin/env python3
"""CPU/memory baseline: 2 x 100 pps synthetic stream through the pipeline."""

from __future__ import annotations

import asyncio
import json
import resource
import sys
import time

from wifi_collector.mock_source import MockFrameSource
from wifi_sensing.calibration import demo_profile
from wifi_sensing.config import FeatureConfig
from wifi_sensing.pipeline import FeaturePipeline


async def run(duration_s: float = 30.0, rate_hz: float = 100.0) -> dict:
    config = FeatureConfig(expected_rate_hz=rate_hz)
    source = MockFrameSource(
        scenario="walk_through",
        seed=0xC5F15EED,
        rate_hz=int(rate_hz),
        duration_s=duration_s,
        real_time=False,
        session_id="bench-sensing",
    )
    manifest = await source.open()
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

    rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return {
        "duration_s": duration_s,
        "rate_hz": rate_hz,
        "frames": frames,
        "windows": windows,
        "elapsed_s": round(elapsed, 6),
        "frames_per_s": round(frames / elapsed, 1) if elapsed else None,
        "windows_per_s": round(windows / elapsed, 1) if elapsed else None,
        "max_rss_bytes": rss,
        "feature_version": config.feature_version,
    }


def main() -> int:
    result = asyncio.run(run())
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
