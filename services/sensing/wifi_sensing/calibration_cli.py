"""wsc-calibration CLI: create, record, annotate, fit, evaluate, activate,
invalidate, list, export."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import cast

from .calibration import CalibrationProfile
from .calibration_session import CalibrationSession, TrialRecord, labels_for_step
from .report import write_report

SESSION_FILE = "session.json"


def _out_dir(args: argparse.Namespace) -> Path:
    return Path(args.out) / str(args.profile_id)


def _save_manifest(session: CalibrationSession, out: Path) -> None:
    (out / "trials_manifest.json").write_text(
        json.dumps(session.trials_manifest(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _load_session(out: Path) -> CalibrationSession:
    data = json.loads((out / SESSION_FILE).read_text(encoding="utf-8"))
    session = CalibrationSession(
        session_id=data["session_id"],
        profile_id=data["profile_id"],
        room_id=data["room_id"],
        topology_hash=data["topology_hash"],
        board_hashes=data["board_hashes"],
        positions=data["positions"],
        firmware_version=data["firmware_version"],
        estimator_version=data["estimator_version"],
        root=out,
        simulated=data["simulated"],
        seed=data["seed"],
        environment=data.get("environment"),
    )
    manifest_path = out / "trials_manifest.json"
    if manifest_path.is_file():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        for trial_id, entry in manifest.items():
            raw_bundle = entry["bundle_dir"]
            bundle = (
                Path(raw_bundle).resolve()
                if Path(raw_bundle).is_absolute()
                else (out / raw_bundle).resolve()
            )
            session.trials[trial_id] = TrialRecord(
                trial_id=trial_id,
                step=entry["step"],
                bundle_dir=bundle,
                label=entry["labels"],
                recorded_at=datetime.fromisoformat(entry["recorded_at"]),
                random_order_index=entry["random_order_index"],
            )
    return session


def _save_profile(out: Path, profile: CalibrationProfile) -> None:
    (out / "profile.json").write_text(
        profile.model_dump_json(indent=2) + "\n",
        encoding="utf-8",
    )


def cmd_create(args: argparse.Namespace) -> int:
    out = _out_dir(args)
    out.mkdir(parents=True, exist_ok=True)
    data = {
        "session_id": args.session_id,
        "profile_id": args.profile_id,
        "room_id": args.room_id,
        "topology_hash": args.topology_hash,
        "board_hashes": {
            "tx": "sha256:" + "0" * 64,
            "rx-a": "sha256:" + "1" * 64,
            "rx-b": "sha256:" + "2" * 64,
        },
        "positions": {
            "rx-a": args.position_rx_a or "corner A, h=1.2m",
            "rx-b": args.position_rx_b or "corner B, h=1.2m",
        },
        "firmware_version": args.firmware_version,
        "estimator_version": args.estimator_version,
        "simulated": args.simulated,
        "seed": args.seed,
        "environment": args.environment,
    }
    (out / SESSION_FILE).write_text(
        json.dumps(data, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(f"created calibration session at {out}")
    return 0


async def _cmd_record(args: argparse.Namespace) -> int:
    out = _out_dir(args)
    session = _load_session(out)
    labels = (
        json.loads(args.labels)
        if args.labels
        else labels_for_step(args.step)
    )
    await session.record_trial(
        trial_id=args.trial_id,
        step=args.step,
        scenario=args.scenario,
        seed=args.seed,
        duration_s=args.duration,
        labels=labels,
    )
    _save_manifest(session, out)
    print(f"recorded trial {args.trial_id}")
    return 0


def cmd_annotate(args: argparse.Namespace) -> int:
    out = _out_dir(args)
    session = _load_session(out)
    trial = session.trials[args.trial_id]
    labels = json.loads(args.labels)
    trial.label = labels
    ground_truth = {
        "schema_version": "ground-truth.v1",
        "trial_id": args.trial_id,
        "session_id": session.session_id,
        "step": trial.step,
        "labels": labels,
        "random_order_index": trial.random_order_index,
        "recorded_at": trial.recorded_at.isoformat(),
    }
    (trial.bundle_dir / "ground_truth.json").write_text(
        json.dumps(ground_truth, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    _save_manifest(session, out)
    print(f"annotated trial {args.trial_id}")
    return 0


async def _cmd_fit(args: argparse.Namespace) -> int:
    out = _out_dir(args)
    session = _load_session(out)
    profile = await session.fit(profile_id=args.profile_id)
    session.activate()
    _save_profile(out, profile)
    _save_manifest(session, out)
    write_report(session, profile, out)
    print(f"fitted {args.profile_id} (checksum {profile.checksum})")
    return 0


def cmd_evaluate(args: argparse.Namespace) -> int:
    out = _out_dir(args)
    profile = CalibrationProfile.model_validate_json(
        (out / "profile.json").read_text(encoding="utf-8")
    )
    if not profile.verify_integrity():
        print("FATAL: profile checksum mismatch", file=sys.stderr)
        return 1
    banner = "SIMULATED — NOT HARDWARE EVIDENCE" if profile.simulated else "LIVE"
    print(f"profile {profile.profile_id} ({banner})")
    metrics = profile.metrics
    if metrics is not None:
        print(f"motion separation: {metrics.motion_separation}")
        print(f"occupancy ordinal accuracy: {metrics.occupancy_ordinal_accuracy}")
        print(f"depth zone accuracy: {metrics.depth_monotonic_accuracy}")
    else:
        print("no metrics stored; run fit first")
    return 0


def cmd_activate(args: argparse.Namespace) -> int:
    out = _out_dir(args)
    profile = CalibrationProfile.model_validate_json(
        (out / "profile.json").read_text(encoding="utf-8")
    )
    if not profile.verify_integrity():
        print("FATAL: profile checksum mismatch", file=sys.stderr)
        return 1
    profile.state = "active"
    profile.checksum = profile.compute_checksum()
    _save_profile(out, profile)
    print(f"activated {args.profile_id}")
    return 0


def cmd_invalidate(args: argparse.Namespace) -> int:
    out = _out_dir(args)
    profile = CalibrationProfile.model_validate_json(
        (out / "profile.json").read_text(encoding="utf-8")
    )
    profile.state = "failed"
    profile.checksum = profile.compute_checksum()
    _save_profile(out, profile)
    (out / "invalidation.json").write_text(
        json.dumps({"reason": args.reason}, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"invalidated {args.profile_id}: {args.reason}")
    return 0


def cmd_list(args: argparse.Namespace) -> int:
    root = Path(args.out)
    for profile_path in sorted(root.glob("*/profile.json")):
        profile = CalibrationProfile.model_validate_json(
            profile_path.read_text(encoding="utf-8")
        )
        print(
            f"{profile.profile_id}\tstate={profile.state}\t"
            f"simulated={profile.simulated}\tfeature={profile.feature_version}"
        )
    return 0


def cmd_export(args: argparse.Namespace) -> int:
    out = _out_dir(args)
    profile = CalibrationProfile.model_validate_json(
        (out / "profile.json").read_text(encoding="utf-8")
    )
    manifest = json.loads((out / "trials_manifest.json").read_text(encoding="utf-8"))
    export = {
        "profile": profile.model_dump(mode="json"),
        "trials": manifest,
        "simulated": profile.simulated,
        "limitations": [
            "occupancy labels are scene disturbance grades, not person counts",
            "depth points are ordinal along the preset axis, not metric depth",
            "simulated metrics are NOT hardware evidence" if profile.simulated
            else "metrics from real hardware",
        ],
    }
    target = Path(args.export_path)
    target.write_text(
        json.dumps(export, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(f"exported to {target}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="wsc-calibration")
    parser.add_argument("--out", default="data/calibration", type=Path)
    sub = parser.add_subparsers(dest="command", required=True)

    create = sub.add_parser("create")
    create.add_argument("--profile-id", required=True)
    create.add_argument("--session-id", default="cal-1")
    create.add_argument("--room-id", default="demo_room_v1")
    create.add_argument("--topology-hash", default="sha256:" + "0" * 64)
    create.add_argument("--position-rx-a", default="")
    create.add_argument("--position-rx-b", default="")
    create.add_argument("--firmware-version", default="wifi-spatial-council-fw/0.1.0")
    create.add_argument("--estimator-version", default="estimator-v1")
    create.add_argument("--simulated", action="store_true")
    create.add_argument("--seed", type=int, default=0xC0FFEE)
    create.add_argument("--environment", default=None)
    create.set_defaults(func=cmd_create)

    record = sub.add_parser("record")
    record.add_argument("--profile-id", required=True)
    record.add_argument("--trial-id", required=True)
    record.add_argument("--step", required=True)
    record.add_argument("--scenario", required=True)
    record.add_argument("--seed", type=int, required=True)
    record.add_argument("--duration", type=float, default=6.0)
    record.add_argument("--labels", default=None)
    record.set_defaults(func=_cmd_record)

    annotate = sub.add_parser("annotate")
    annotate.add_argument("--profile-id", required=True)
    annotate.add_argument("--trial-id", required=True)
    annotate.add_argument("--labels", required=True)
    annotate.set_defaults(func=cmd_annotate)

    fit = sub.add_parser("fit")
    fit.add_argument("--profile-id", required=True)
    fit.set_defaults(func=_cmd_fit)

    evaluate = sub.add_parser("evaluate")
    evaluate.add_argument("--profile-id", required=True)
    evaluate.set_defaults(func=cmd_evaluate)

    activate = sub.add_parser("activate")
    activate.add_argument("--profile-id", required=True)
    activate.set_defaults(func=cmd_activate)

    invalidate = sub.add_parser("invalidate")
    invalidate.add_argument("--profile-id", required=True)
    invalidate.add_argument("--reason", default="manual invalidation")
    invalidate.set_defaults(func=cmd_invalidate)

    sub.add_parser("list").set_defaults(func=cmd_list)

    export = sub.add_parser("export")
    export.add_argument("--profile-id", required=True)
    export.add_argument("--export-path", required=True, type=Path)
    export.set_defaults(func=cmd_export)

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    func = args.func
    if asyncio.iscoroutinefunction(func):
        return cast(int, asyncio.run(func(args)))
    return cast(int, func(args))


if __name__ == "__main__":
    sys.exit(main())
