"""Sliding windows: chunk invariance and boundary semantics."""

from __future__ import annotations

import asyncio

from wifi_collector.mock_source import MockFrameSource
from wifi_sensing.calibration import demo_profile
from wifi_sensing.cleaning import CleaningTransformer
from wifi_sensing.config import FeatureConfig
from wifi_sensing.pipeline import FeaturePipeline
from wifi_sensing.windows import SlidingWindowBuffer


def _cleaned_frames() -> list:
    async def build() -> list:
        source = MockFrameSource(
            scenario="idle",
            seed=3,
            rate_hz=100,
            duration_s=5.0,
            real_time=False,
        )
        manifest = await source.open()
        cleaner = CleaningTransformer(FeatureConfig())
        cleaned = []
        async for frame in source.frames():
            item = cleaner.clean(frame, manifest)
            if item is not None:
                cleaned.append(item)
        return cleaned

    return asyncio.run(build())


async def _pipeline_windows(batch_size: int) -> list[dict]:
    source = MockFrameSource(
        scenario="idle",
        seed=3,
        rate_hz=100,
        duration_s=5.0,
        real_time=False,
    )
    manifest = await source.open()
    config = FeatureConfig()
    profile = demo_profile(config, manifest.topology_hash)
    pipeline = FeaturePipeline(config, profile)
    windows = []
    batch = []
    async for frame in source.frames():
        batch.append(frame)
        if len(batch) >= batch_size:
            windows.extend(pipeline.transform(batch, manifest))
            batch = []
    windows.extend(pipeline.transform(batch, manifest))
    await source.close()
    return [window.model_dump(mode="json") for window in windows]


def test_chunk_invariance() -> None:
    one_by_one = asyncio.run(_pipeline_windows(1))
    batches_of_seven = asyncio.run(_pipeline_windows(7))
    one_big_chunk = asyncio.run(_pipeline_windows(1000))
    assert one_by_one == batches_of_seven == one_big_chunk
    assert len(one_by_one) >= 10  # 5 s stream, 2 s window, 0.25 stride


def test_windows_never_include_future_frames() -> None:
    frames = _cleaned_frames()
    config = FeatureConfig(window_s=2.0, stride_ms=500)
    buffer = SlidingWindowBuffer(config)
    emitted: list = []
    # Feed only the first half; no window whose end exceeds the newest ts.
    for frame in frames[: int(len(frames) * 0.5)]:
        emitted.extend(buffer.push(frame))
    for window in emitted:
        newest = max(
            item.ts_ns for items in window.frames.values() for item in items
        )
        assert newest <= frames[int(len(frames) * 0.5) - 1].ts_ns


def test_flush_emits_partial_window() -> None:
    frames = _cleaned_frames()
    config = FeatureConfig(window_s=2.0, stride_ms=250)
    buffer = SlidingWindowBuffer(config)
    for frame in frames:
        buffer.push(frame)
    flushed = buffer.flush()
    assert flushed
    assert buffer.flush() == []
