"""Two runs of the pipeline produce identical windows; CLI is reproducible."""

from __future__ import annotations

import asyncio
import json
import subprocess
import sys
from pathlib import Path

from wifi_collector.mock_source import MockFrameSource
from wifi_sensing.calibration import demo_profile
from wifi_sensing.config import FeatureConfig
from wifi_sensing.pipeline import FeaturePipeline

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = ROOT / "data" / "fixtures" / "walk_through"


def _windows_once(seed: int):
    async def build() -> list:
        source = MockFrameSource(
            scenario="walk_through",
            seed=seed,
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
        return [w.model_dump(mode="json") for w in windows]

    return asyncio.run(build())


def test_pipeline_runs_are_identical() -> None:
    assert _windows_once(42) == _windows_once(42)


def test_extract_features_cli_is_reproducible(tmp_path: Path) -> None:
    def run(out: Path) -> Path:
        result = subprocess.run(
            [
                sys.executable,
                "scripts/extract_features.py",
                "--replay",
                str(FIXTURE),
                "--recompute",
                "--output",
                str(out),
            ],
            cwd=ROOT,
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, result.stderr
        return out / "session-fixture-walk-through" / "features.parquet"

    first = run(tmp_path / "a")
    second = run(tmp_path / "b")
    assert first.read_bytes() == second.read_bytes()
    qa = json.loads(
        (first.parent / "qa_report.json").read_text(encoding="utf-8")
    )
    assert qa["windows"] > 0
    assert qa["replay_sha256"]
