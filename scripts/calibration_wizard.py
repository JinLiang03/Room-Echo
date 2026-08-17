#!/usr/bin/env python3
"""Text-guided calibration wizard; --mode mock is fully automated (CI)."""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import sys
from pathlib import Path

from wifi_sensing.calibration_session import (
    CalibrationSession,
    build_mock_plan,
)
from wifi_sensing.config import FeatureConfig
from wifi_sensing.quality import check_trial_quality
from wifi_sensing.report import write_report


def _fake_hash(label: str) -> str:
    return "sha256:" + hashlib.sha256(label.encode("utf-8")).hexdigest()


async def _run_mock(args: argparse.Namespace) -> int:
    out_dir = Path(args.out) / args.scenario
    config = FeatureConfig()
    session = CalibrationSession(
        session_id=f"mock-{args.scenario}",
        profile_id=args.scenario,
        room_id=args.scenario,
        # Use the same topology as the deterministic mock fixtures so the
        # calibrated profile can be replayed against them.
        topology_hash=_fake_hash("topology-two-rx-mock"),
        board_hashes={
            "tx": _fake_hash("tx"),
            "rx-a": _fake_hash("rx-a"),
            "rx-b": _fake_hash("rx-b"),
        },
        positions={"rx-a": "corner A, h=1.2m", "rx-b": "corner B, h=1.2m"},
        firmware_version="wifi-spatial-council-fw/0.1.0",
        estimator_version="estimator-v1",
        root=out_dir,
        simulated=True,
        seed=args.seed,
        environment="simulated CI room (not hardware)",
        config=config,
    )
    plan = build_mock_plan(
        base_seed=args.seed,
        duration_s=args.duration_s,
        rounds_per_step=args.rounds,
    )
    print("== Calibration wizard (mode=mock, simulated=true) ==")
    print(f"profile: {args.scenario} | trials: {len(plan)} | seed: {args.seed:#x}")
    for index, item in enumerate(plan, start=1):
        print(
            f"[{index}/{len(plan)}] {item['step']:<16} "
            f"(seed {item['seed']}, {item['duration_s']:.0f}s simulated)"
        )
        trial_id = f"trial-{item['random_order_index']:03d}-{item['step']}"
        record = await session.record_trial(trial_id=trial_id, **item)
        ok, reasons = await check_trial_quality(record.bundle_dir, config)
        if not ok:
            print(f"  quality precheck FAILED: {reasons}; re-recording once")
            retry = {**item, "seed": item["seed"] + 100_000}
            record = await session.record_trial(
                trial_id=f"{trial_id}-retry",
                **retry,
            )
            ok, reasons = await check_trial_quality(record.bundle_dir, config)
            if not ok:
                session.invalidate(f"trial {trial_id} failed precheck: {reasons}")
                print(f"FATAL: {reasons}", file=sys.stderr)
                return 1

    print("fitting baseline mappings (train+validation only)...")
    profile = await session.fit()
    session.activate()
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "profile.json").write_text(
        profile.model_dump_json(indent=2) + "\n",
        encoding="utf-8",
    )
    (out_dir / "trials_manifest.json").write_text(
        json.dumps(session.trials_manifest(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    write_report(session, profile, out_dir)
    print("== SIMULATED CALIBRATION COMPLETE — NOT HARDWARE EVIDENCE ==")
    metrics = profile.metrics
    print(f"motion separation: {metrics.motion_separation}")
    print(f"occupancy ordinal accuracy: {metrics.occupancy_ordinal_accuracy}")
    print(f"depth zone accuracy: {metrics.depth_monotonic_accuracy}")
    print(f"profile checksum: {profile.checksum}")
    print(f"report: {out_dir / 'calibration_report.json'}")
    print(f"html: {out_dir / 'calibration_report.html'}")
    return 0


async def _run_live(_args: argparse.Namespace) -> int:
    print(
        "live calibration requires ESP32 hardware and Phase 11 validation; "
        "use --mode mock for now.",
        file=sys.stderr,
    )
    return 2


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("mock", "live"), default="mock")
    parser.add_argument("--scenario", default="demo_room_v1")
    parser.add_argument("--out", default="data/calibration", type=Path)
    parser.add_argument("--duration-s", type=float, default=6.0)
    parser.add_argument("--seed", type=int, default=0xC0FFEE)
    parser.add_argument("--rounds", type=int, default=2)
    args = parser.parse_args(argv)
    if args.mode == "live":
        return asyncio.run(_run_live(args))
    return asyncio.run(_run_mock(args))


if __name__ == "__main__":
    sys.exit(main())
