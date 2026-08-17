"""Shared profile and stream helpers for signal tests."""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest
from wifi_collector.mock_source import MockFrameSource
from wifi_sensing.calibration import CalibrationProfile
from wifi_sensing.config import FeatureConfig
from wifi_sensing.pipeline import FeaturePipeline
from wifi_sensing.signal_config import SignalConfig
from wifi_sensing.signal_triplet import SignalEstimator

PROFILE_PATH = Path(__file__).parent / "fixtures" / "profile.json"


@pytest.fixture(scope="session")
def profile() -> CalibrationProfile:
    loaded = CalibrationProfile.model_validate_json(
        PROFILE_PATH.read_text(encoding="utf-8")
    )
    assert loaded.verify_integrity()
    return loaded


@pytest.fixture(scope="session")
def signal_estimator(profile: CalibrationProfile) -> SignalEstimator:
    return SignalEstimator(SignalConfig(), profile)


def run_stream(
    scenario: str,
    seed: int,
    duration: float,
    profile: CalibrationProfile,
    estimator: SignalEstimator,
    *,
    keep_links: tuple[str, ...] | None = None,
    source_topology_hash: str | None = None,
):
    async def _run() -> list:
        estimator.reset()
        source = MockFrameSource(
            scenario=scenario,
            seed=seed,
            duration_s=duration,
            real_time=False,
            topology_hash=source_topology_hash or profile.topology_hash,
        )
        manifest = await source.open()
        pipeline = FeaturePipeline(FeatureConfig(), profile)
        windows = []
        async for frame in source.frames():
            if keep_links is not None and frame.link_id not in keep_links:
                continue
            windows.extend(pipeline.transform([frame], manifest))
        triplets = [estimator.estimate(window) for window in windows]
        await source.close()
        return triplets

    return asyncio.run(_run())
