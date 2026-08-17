#!/usr/bin/env python3
"""Extract FeatureWindows from a replay bundle (recompute from raw)."""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import sys
import time
from pathlib import Path

from wifi_collector.replay_bundle import RAW_FILE, BundleVerifier
from wifi_collector.replay_source import ReplayFrameSource
from wifi_sensing.calibration import CalibrationProfile, demo_profile
from wifi_sensing.config import FeatureConfig
from wifi_sensing.parquet_io import windows_to_parquet
from wifi_sensing.pipeline import FeaturePipeline


def _load_profile(
    path: str | None,
    config: FeatureConfig,
    topology_hash: str,
) -> CalibrationProfile:
    if path is None:
        return demo_profile(config, topology_hash)
    profile = CalibrationProfile.model_validate_json(
        Path(path).read_text(encoding="utf-8")
    )
    if profile.feature_version != config.feature_version:
        raise SystemExit(
            f"profile feature_version {profile.feature_version!r} != "
            f"config {config.feature_version!r}"
        )
    return profile


async def _run(args: argparse.Namespace) -> int:
    bundle = Path(args.replay)
    verify = BundleVerifier(bundle).verify()
    if not verify.ok:
        print(f"bundle verification failed: {'; '.join(verify.errors)}", file=sys.stderr)
        return 1

    config = FeatureConfig(
        window_s=args.window_s,
        stride_ms=args.stride_ms,
        expected_rate_hz=args.expected_rate,
    )
    source = ReplayFrameSource(bundle, real_time=False, recompute=args.recompute)
    manifest = await source.open()
    if args.start_s:
        source.seek(args.start_s)
    profile = _load_profile(args.profile, config, manifest.topology_hash)
    pipeline = FeaturePipeline(config, profile)

    windows = []
    start_wall = time.perf_counter()
    frame_count = 0
    async for frame in source.frames():
        if args.end_s is not None and frame.device_ts_us / 1_000_000 > args.end_s:
            break
        frame_count += 1
        windows.extend(pipeline.transform([frame], manifest))
    elapsed = time.perf_counter() - start_wall
    await source.close()

    raw_sha = hashlib.sha256((bundle / RAW_FILE).read_bytes()).hexdigest()
    out_dir = Path(args.output) / manifest.session_id
    out_dir.mkdir(parents=True, exist_ok=True)
    windows_to_parquet(
        windows,
        out_dir / "features.parquet",
        source=f"replay:{manifest.source_mode}",
        extra={
            "feature_version": config.feature_version,
            "profile_id": profile.profile_id,
            "profile_source": profile.source,
            "topology_hash": profile.topology_hash,
            "recompute": args.recompute,
            "replay_sha256": raw_sha,
            "frames_processed": frame_count,
            "elapsed_s": round(elapsed, 6),
        },
    )

    flag_counts: dict[str, int] = {}
    link_count = 0
    for window in windows:
        for link in window.links.values():
            link_count += 1
            for flag in link.quality_flags:
                flag_counts[flag] = flag_counts.get(flag, 0) + 1

    qa = {
        "bundle": str(bundle),
        "replay_sha256": raw_sha,
        "feature_version": config.feature_version,
        "profile": {"id": profile.profile_id, "source": profile.source},
        "windows": len(windows),
        "frames_processed": frame_count,
        "quality_flag_counts": flag_counts,
        "paired_windows": sum(1 for w in windows if w.paired is not None),
        "elapsed_s": round(elapsed, 6),
        "output": str(out_dir / "features.parquet"),
    }
    (out_dir / "qa_report.json").write_text(
        json.dumps(qa, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(
        f"extracted {len(windows)} windows from {frame_count} frames "
        f"({elapsed * 1000:.1f} ms) -> {out_dir / 'features.parquet'}"
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--replay", required=True, type=Path)
    parser.add_argument("--output", default="data/derived/features", type=Path)
    parser.add_argument("--profile", default=None, help="CalibrationProfile JSON")
    parser.add_argument(
        "--recompute",
        action="store_true",
        help="recompute features from raw (always the case; flag records intent)",
    )
    parser.add_argument("--start-s", type=float, default=None)
    parser.add_argument("--end-s", type=float, default=None)
    parser.add_argument("--window-s", type=float, default=2.0)
    parser.add_argument("--stride-ms", type=int, default=250)
    parser.add_argument("--expected-rate", type=float, default=100.0)
    args = parser.parse_args(argv)
    return asyncio.run(_run(args))


if __name__ == "__main__":
    sys.exit(main())
