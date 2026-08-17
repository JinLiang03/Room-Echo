"""FeatureWindow parquet round-trip with schema version."""

from __future__ import annotations

import asyncio
from pathlib import Path

from wifi_collector.mock_source import MockFrameSource
from wifi_sensing.calibration import demo_profile
from wifi_sensing.config import FeatureConfig
from wifi_sensing.parquet_io import parquet_to_windows, windows_to_parquet
from wifi_sensing.pipeline import FeaturePipeline


def _windows():
    async def build() -> list:
        source = MockFrameSource(
            scenario="walk_through",
            seed=5,
            rate_hz=100,
            duration_s=3.0,
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

    return asyncio.run(build())


def test_parquet_round_trip(tmp_path: Path) -> None:
    windows = _windows()
    assert windows
    path = tmp_path / "features.parquet"
    windows_to_parquet(
        windows,
        path,
        source="replay:mock",
        extra={"feature_version": "features-v2"},
    )
    restored = parquet_to_windows(path)
    assert [w.model_dump(mode="json") for w in restored] == [
        w.model_dump(mode="json") for w in windows
    ]


def test_meta_version_mismatch_rejected(tmp_path: Path) -> None:
    windows = _windows()
    path = tmp_path / "features.parquet"
    windows_to_parquet(windows, path, source="replay:mock")
    meta = tmp_path / "features.meta.json"
    meta.write_text('{"schema_version": "9.9.9"}', encoding="utf-8")
    import pytest

    with pytest.raises(ValueError, match="unsupported feature schema"):
        parquet_to_windows(path)
