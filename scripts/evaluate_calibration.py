#!/usr/bin/env python3
"""Re-evaluate a stored calibration profile on its held-out trials."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

from wifi_collector.replay_source import ReplayFrameSource
from wifi_sensing.calibration import CalibrationProfile
from wifi_sensing.config import FeatureConfig
from wifi_sensing.evaluate import recompute_metrics
from wifi_sensing.pipeline import FeaturePipeline


async def _run(args: argparse.Namespace) -> int:
    out_dir = Path(args.profile)
    profile_path = out_dir / "profile.json"
    manifest_path = out_dir / "trials_manifest.json"
    if not profile_path.is_file() or not manifest_path.is_file():
        print(
            f"missing profile.json or trials_manifest.json in {out_dir}",
            file=sys.stderr,
        )
        return 1
    profile = CalibrationProfile.model_validate_json(
        profile_path.read_text(encoding="utf-8")
    )
    if not profile.verify_integrity():
        print("FATAL: profile checksum mismatch", file=sys.stderr)
        return 1
    config = FeatureConfig()
    if profile.feature_version != config.feature_version:
        print(
            f"FATAL: profile feature_version {profile.feature_version!r} != "
            f"config {config.feature_version!r}",
            file=sys.stderr,
        )
        return 1

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    held_out = (
        profile.metrics.held_out_trial_ids
        if profile.metrics is not None
        else sorted(manifest)
    )
    step_of = {trial_id: entry["step"] for trial_id, entry in manifest.items()}
    windows_by_trial = {}
    for trial_id in held_out:
        entry = manifest.get(trial_id)
        if entry is None:
            continue
        raw_bundle = entry["bundle_dir"]
        bundle = (
            Path(raw_bundle).resolve()
            if Path(raw_bundle).is_absolute()
            else (out_dir / raw_bundle).resolve()
        )
        source = ReplayFrameSource(bundle, real_time=False)
        source_manifest = await source.open()
        pipeline = FeaturePipeline(config, profile)
        windows = []
        async for frame in source.frames():
            windows.extend(pipeline.transform([frame], source_manifest))
        await source.close()
        windows_by_trial[trial_id] = windows

    if profile.fit_parameters is None:
        print("FATAL: profile has no fit parameters", file=sys.stderr)
        return 1
    metrics = recompute_metrics(
        profile.fit_parameters,
        simulated=profile.simulated,
        test_trial_ids=held_out,
        windows_by_trial=windows_by_trial,
        step_of=step_of,
    )
    banner = (
        "SIMULATED — NOT HARDWARE EVIDENCE"
        if profile.simulated
        else "LIVE"
    )
    print(f"profile {profile.profile_id} ({banner})")
    print(f"motion separation: {metrics.motion_separation}")
    print(f"occupancy ordinal accuracy: {metrics.occupancy_ordinal_accuracy}")
    print(f"depth zone accuracy: {metrics.depth_monotonic_accuracy}")
    print(f"held-out trials: {metrics.held_out_trial_ids}")
    (out_dir / "evaluation_rerun.json").write_text(
        json.dumps(metrics.model_dump(mode="json"), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--profile",
        default="data/calibration/demo_room_v1",
        type=Path,
    )
    args = parser.parse_args(argv)
    return asyncio.run(_run(args))


if __name__ == "__main__":
    sys.exit(main())
