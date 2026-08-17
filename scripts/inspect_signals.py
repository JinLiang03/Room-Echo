#!/usr/bin/env python3
"""Replay a bundle, estimate the three proxy signals, and write a QA report."""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import html
import json
import sys
from pathlib import Path

from wifi_collector.replay_bundle import RAW_FILE, BundleVerifier
from wifi_collector.replay_source import ReplayFrameSource
from wifi_sensing.calibration import CalibrationProfile, demo_profile
from wifi_sensing.config import FeatureConfig
from wifi_sensing.model_card import build_model_card, write_model_card
from wifi_sensing.pipeline import FeaturePipeline
from wifi_sensing.signal_config import SignalConfig
from wifi_sensing.signal_evidence import (
    EvidenceBuilder,
    EvidenceLog,
    EvidenceTrigger,
)
from wifi_sensing.signal_triplet import SignalEstimator


def _load_profile(args: argparse.Namespace, topology_hash: str) -> CalibrationProfile:
    config = FeatureConfig()
    if args.profile:
        profile_dir = Path(args.profile)
        profile_path = (
            profile_dir / "profile.json"
            if profile_dir.is_dir()
            else profile_dir
        )
        if profile_path.is_file():
            profile = CalibrationProfile.model_validate_json(
                profile_path.read_text(encoding="utf-8")
            )
            if not profile.verify_integrity():
                raise SystemExit("profile checksum mismatch")
            if profile.topology_hash != topology_hash:
                print(
                    "WARNING: profile topology does not match replay; "
                    "falling back to demo profile",
                    file=sys.stderr,
                )
                return demo_profile(config, topology_hash)
            return profile
    stored = (
        Path("data/calibration/demo_room_v1") / "profile.json"
    )
    if stored.is_file():
        profile = CalibrationProfile.model_validate_json(
            stored.read_text(encoding="utf-8")
        )
        if profile.verify_integrity() and profile.topology_hash == topology_hash:
            return profile
    return demo_profile(config, topology_hash)


def _svg_line(values: list[float], width: int = 640, height: int = 120) -> str:
    if not values:
        return "<text>no data</text>"
    points = []
    for index, value in enumerate(values):
        x = index * (width / max(len(values) - 1, 1))
        y = height - value * (height - 8) - 4
        points.append(f"{x:.1f},{y:.1f}")
    return (
        f'<svg width="{width}" height="{height}" viewBox="0 0 {width} {height}">'
        f'<polyline fill="none" stroke="#2563eb" stroke-width="1.5" '
        f'points="{" ".join(points)}"/></svg>'
    )


def _render_html(qa: dict, model_card: dict, evidence_hashes: list[str]) -> str:
    motion = [t["motion"]["value"] for t in qa["triplets"]]
    occupancy = [
        t["occupancy_density"]["probabilities"]["unknown"] for t in qa["triplets"]
    ]
    depth = [t["depth_zone"]["probabilities"]["unknown"] for t in qa["triplets"]]
    status_rows = "".join(
        f"<tr><td>{index}</td><td>{t['motion']['state']}</td>"
        f"<td>{t['occupancy_density']['state']}</td>"
        f"<td>{t['depth_zone']['state']}</td>"
        f"<td>{t['status']}</td><td>{t['sensor_confidence_cap']}</td></tr>"
        for index, t in enumerate(qa["triplets"])
    )
    banner = (
        "SIMULATED — NOT HARDWARE EVIDENCE"
        if qa["simulated"]
        else "LIVE"
    )
    return f"""<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8">
<title>Signal QA — {html.escape(qa['profile_id'])}</title>
<style>body{{font-family:system-ui,sans-serif;max-width:980px;margin:2rem auto;
padding:0 1rem}}table{{border-collapse:collapse;font-size:.85rem}}
th,td{{border:1px solid #ccc;padding:.3rem .5rem}}h3{{margin-top:1.5rem}}
.badge{{display:inline-block;padding:.15rem .6rem;border-radius:999px;
background:#fde68a;font-weight:600}}</style></head><body>
<h1>Signal QA — {html.escape(qa['profile_id'])}</h1>
<p><span class="badge">{banner}</span> · estimator
{html.escape(qa['estimator_version'])} · replay
<code>{html.escape(qa['replay_sha256'][:16])}</code></p>
<h3>Motion intensity (value)</h3>{_svg_line(motion)}
<h3>Occupancy unknown probability</h3>{_svg_line(occupancy)}
<h3>Depth unknown probability</h3>{_svg_line(depth)}
<h3>Triplets ({qa['triplet_count']})</h3>
<table><thead><tr><th>#</th><th>motion</th><th>occupancy</th><th>depth</th>
<th>status</th><th>cap</th></tr></thead><tbody>{status_rows}</tbody></table>
<h3>Evidence seals</h3>
<ul>{''.join(f'<li><code>{hash_}</code></li>' for hash_ in evidence_hashes[-10:])}</ul>
<h3>Model card</h3><pre>{html.escape(json.dumps(model_card, indent=2))}</pre>
</body></html>
"""


async def _run(args: argparse.Namespace) -> int:
    bundle = Path(args.replay)
    verify = BundleVerifier(bundle).verify()
    if not verify.ok:
        print(
            f"bundle verification failed: {'; '.join(verify.errors)}",
            file=sys.stderr,
        )
        return 1

    config = FeatureConfig()
    signal_config = SignalConfig()
    source = ReplayFrameSource(bundle, real_time=False, recompute=args.recompute)
    manifest = await source.open()
    profile = _load_profile(args, manifest.topology_hash)
    pipeline = FeaturePipeline(config, profile)
    estimator = SignalEstimator(signal_config, profile)
    trigger = EvidenceTrigger(signal_config)
    builder = EvidenceBuilder(profile, manifest)
    log = EvidenceLog(
        Path(args.evidence_log)
        if args.evidence_log
        else Path("data/derived/evidence") / f"{manifest.session_id}.jsonl"
    )

    windows = []
    triplets = []
    evidence_hashes: list[str] = []
    sequence = 0
    cycle = 0
    previous = None
    last_seal_s = None
    now_s = 0.0

    async for frame in source.frames():
        for window in pipeline.transform([frame], manifest):
            windows.append(window)
            now_s = window.end_ns / 1_000_000_000
            triplet = estimator.estimate(window)
            triplets.append(triplet)
            if trigger.should_seal(
                triplet,
                previous,
                now_s=now_s,
                last_seal_s=last_seal_s,
            ):
                cycle += 1
                sequence += 1
                packet = builder.build(
                    triplet,
                    window,
                    sequence=sequence,
                    cycle_id=f"cycle-{cycle:04d}",
                )
                log.write(packet)
                evidence_hashes.append(packet.evidence_hash)
                last_seal_s = now_s
            previous = triplet
    await source.close()

    # Staleness: clear previous state with an unknown triplet.
    if triplets:
        stale = estimator.estimate_stale(
            session_id=manifest.session_id,
            source_mode=manifest.source_mode,
        )
        triplets.append(stale)
        if trigger.should_seal(
            stale,
            previous,
            now_s=now_s + 100.0,
            last_seal_s=last_seal_s,
        ):
            cycle += 1
            sequence += 1
            packet = builder.build(
                stale,
                windows[-1],
                sequence=sequence,
                cycle_id=f"cycle-{cycle:04d}",
            )
            log.write(packet)
            evidence_hashes.append(packet.evidence_hash)

    raw_sha = hashlib.sha256((bundle / RAW_FILE).read_bytes()).hexdigest()
    state_counts: dict[str, int] = {}
    for triplet in triplets:
        for state in (
            triplet.motion.state,
            triplet.occupancy_density.state,
            triplet.depth_zone.state,
        ):
            state_counts[state] = state_counts.get(state, 0) + 1
    status_counts: dict[str, int] = {}
    for triplet in triplets:
        status_counts[triplet.status] = status_counts.get(triplet.status, 0) + 1
    unknown_flags = {
        "motion": sum(1 for t in triplets if t.motion.state == "unknown"),
        "occupancy": sum(
            1 for t in triplets if t.occupancy_density.state == "unknown"
        ),
        "depth": sum(1 for t in triplets if t.depth_zone.state == "unknown"),
    }
    qa = {
        "schema_version": "signal-qa.v1",
        "profile_id": profile.profile_id,
        "simulated": profile.simulated,
        "estimator_version": (
            f"{signal_config.version}/{profile.estimator_version}/{config.feature_version}"
        ),
        "replay_sha256": raw_sha,
        "triplet_count": len(triplets),
        "window_count": len(windows),
        "evidence_seals": len(evidence_hashes),
        "state_counts": state_counts,
        "status_counts": status_counts,
        "unknown_counts": unknown_flags,
        "triplets": [triplet.model_dump(mode="json") for triplet in triplets],
        "limitations": [
            "simulated replay QA; not hardware evidence" if profile.simulated
            else "hardware replay QA",
        ],
    }
    model_card = build_model_card(
        profile,
        signal_config,
        source="replay",
        metrics=profile.metrics.model_dump(mode="json") if profile.metrics else None,
    )

    report_path = Path(args.report)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    (report_path.parent / "signal_qa.json").write_text(
        json.dumps(qa, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    write_model_card(model_card, report_path.parent / "model_card.json")
    report_path.write_text(_render_html(qa, model_card, evidence_hashes), encoding="utf-8")
    banner = "SIMULATED — NOT HARDWARE EVIDENCE" if profile.simulated else "LIVE"
    print(f"{banner}")
    print(
        f"triplets={len(triplets)} windows={len(windows)} "
        f"evidence_seals={len(evidence_hashes)}"
    )
    print(f"unknown counts: {unknown_flags}")
    print(f"status counts: {status_counts}")
    if evidence_hashes:
        print(f"example evidence hash: {evidence_hashes[0]}")
    print(f"report: {report_path}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--replay", required=True, type=Path)
    parser.add_argument("--report", default="artifacts/signal_qa.html", type=Path)
    parser.add_argument("--profile", default=None, type=Path)
    parser.add_argument("--evidence-log", default=None, type=Path)
    parser.add_argument("--recompute", action="store_true")
    args = parser.parse_args(argv)
    return asyncio.run(_run(args))


if __name__ == "__main__":
    sys.exit(main())
