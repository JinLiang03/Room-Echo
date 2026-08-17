#!/usr/bin/env python3
"""Replay a bundle, seal evidence, and run the agent council end to end."""

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
from wifi_council.config import CouncilConfig
from wifi_council.runtime import CouncilRuntime, build_provider
from wifi_sensing.calibration import CalibrationProfile, demo_profile
from wifi_sensing.config import FeatureConfig
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
    stored = Path("data/calibration/demo_room_v1") / "profile.json"
    if stored.is_file():
        profile = CalibrationProfile.model_validate_json(
            stored.read_text(encoding="utf-8")
        )
        if profile.verify_integrity() and profile.topology_hash == topology_hash:
            return profile
    return demo_profile(config, topology_hash)


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
    council_config = CouncilConfig(max_calls_per_cycle=args.budget)
    source = ReplayFrameSource(bundle, real_time=False, recompute=args.recompute)
    manifest = await source.open()
    profile = _load_profile(args, manifest.topology_hash)
    pipeline = FeaturePipeline(config, profile)
    estimator = SignalEstimator(signal_config, profile)
    trigger = EvidenceTrigger(signal_config)
    builder = EvidenceBuilder(profile, manifest)

    audit_path = (
        Path(args.audit_log)
        if args.audit_log
        else Path("data/derived/council") / f"{manifest.session_id}.audit.jsonl"
    )
    provider = build_provider(council_config, args.provider)
    runtime = CouncilRuntime(
        council_config,
        provider=provider,
        audit_path=audit_path,
    )
    scheduler = runtime.scheduler

    evidence_log = EvidenceLog(
        Path(args.evidence_log)
        if args.evidence_log
        else Path("data/derived/evidence") / f"{manifest.session_id}.jsonl"
    )

    sequence = 0
    cycle = 0
    previous = None
    last_seal_s = None
    now_s = 0.0
    sealed = 0
    last_window = None

    async for frame in source.frames():
        for window in pipeline.transform([frame], manifest):
            last_window = window
            now_s = window.end_ns / 1_000_000_000
            triplet = estimator.estimate(window)
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
                evidence_log.write(packet)
                scheduler.submit(packet)
                sealed += 1
                last_seal_s = now_s
            previous = triplet
    await source.close()

    # Final stale seal clears state with an unknown triplet.
    if previous is not None and last_window is not None:
        stale = estimator.estimate_stale(
            session_id=manifest.session_id,
            source_mode=manifest.source_mode,
        )
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
                last_window,
                sequence=sequence,
                cycle_id=f"cycle-{cycle:04d}",
            )
            evidence_log.write(packet)
            scheduler.submit(packet)
            sealed += 1

    if not await scheduler.wait_idle(timeout_s=args.idle_timeout):
        print("council did not become idle in time", file=sys.stderr)
        return 1

    cycles = [
        detail
        for detail in (
            runtime.store.get(cycle_id)
            for cycle_id in runtime.store.cycle_ids(limit=10_000)
        )
        if detail is not None
    ]
    cycles.sort(key=lambda item: item.cycle_id)
    raw_sha = hashlib.sha256((bundle / RAW_FILE).read_bytes()).hexdigest()
    status_counts: dict[str, int] = {}
    rejection_counts: dict[str, int] = {}
    for detail in cycles:
        status_counts[detail.status] = status_counts.get(detail.status, 0) + 1
        for rejection in detail.rejections:
            rejection_counts[rejection.reason_code] = (
                rejection_counts.get(rejection.reason_code, 0) + 1
            )

    qa = {
        "schema_version": "council-qa.v1",
        "provider": provider.name,
        "provider_models": list(
            dict.fromkeys(
                record.model
                for detail in cycles
                for record in detail.calls
            )
        ),
        "council_config_version": council_config.version,
        "profile_id": profile.profile_id,
        "simulated": profile.simulated,
        "replay_sha256": raw_sha,
        "cycles": [detail.model_dump(mode="json") for detail in cycles],
        "cycle_count": len(cycles),
        "evidence_sealed": sealed,
        "status_counts": status_counts,
        "rejection_counts": rejection_counts,
        "usage": runtime.store.usage_summary().model_dump(mode="json"),
        "limitations": [
            "simulated replay council; not hardware evidence"
            if profile.simulated
            else "hardware replay council",
        ],
    }

    report_path = Path(args.report)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    (report_path.parent / "council_qa.json").write_text(
        json.dumps(qa, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    report_path.write_text(_render_html(qa), encoding="utf-8")

    banner = "SIMULATED — NOT HARDWARE EVIDENCE" if profile.simulated else "LIVE"
    print(banner)
    print(
        f"provider={provider.name} cycles={len(cycles)} sealed={sealed} "
        f"status={status_counts}"
    )
    print(f"rejections by reason: {rejection_counts}")
    if cycles:
        first = cycles[0]
        print(
            f"example cycle {first.cycle_id}: {first.status} "
            f"display={first.result.display_confidence if first.result else None}"
        )
    print(f"report: {report_path}")
    return 0


def _render_html(qa: dict) -> str:
    banner = "SIMULATED — NOT HARDWARE EVIDENCE" if qa["simulated"] else "LIVE"
    rows = ""
    for detail in qa["cycles"]:
        result: dict | None = detail.get("result")
        display = (
            f"{result['display_confidence']:.3f}" if result is not None else "—"
        )
        model_support = (
            f"{result['model_support']:.3f}" if result is not None else "—"
        )
        cap = (
            f"{result['sensor_confidence_cap']:.3f}"
            if result is not None
            else "—"
        )
        participants = (
            result["interpretation_agreement"]["participants"]
            if result is not None
            else 0
        )
        claims = len(detail.get("claims", []))
        challenges = len(detail.get("challenges", []))
        rejections = len(detail.get("rejections", []))
        rows += (
            f"<tr><td>{html.escape(detail['cycle_id'])}</td>"
            f"<td>{html.escape(detail['status'])}</td>"
            f"<td>{cap}</td><td>{model_support}</td><td>{display}</td>"
            f"<td>{participants}</td><td>{claims}</td><td>{challenges}</td>"
            f"<td>{rejections}</td>"
            f"<td>{html.escape(detail.get('phase', ''))}</td></tr>"
        )
    return f"""<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8">
<title>Council QA — {html.escape(str(qa['profile_id']))}</title>
<style>body{{font-family:system-ui,sans-serif;max-width:1100px;margin:2rem auto;
padding:0 1rem}}table{{border-collapse:collapse;font-size:.82rem;width:100%}}
th,td{{border:1px solid #ccc;padding:.3rem .45rem;text-align:left}}
.badge{{display:inline-block;padding:.15rem .6rem;border-radius:999px;
background:#fde68a;font-weight:600}}h3{{margin-top:1.5rem}}</style></head><body>
<h1>Council QA — {html.escape(str(qa['profile_id']))}</h1>
<p><span class="badge">{banner}</span> · provider
<code>{html.escape(qa['provider'])}</code> · replay
<code>{html.escape(str(qa['replay_sha256'])[:16])}</code></p>
<h3>Cycles ({qa['cycle_count']})</h3>
<table><thead><tr><th>cycle</th><th>status</th><th>cap</th><th>support</th>
<th>display</th><th>agents</th><th>claims</th><th>challenges</th>
<th>rejections</th><th>phase</th></tr></thead><tbody>{rows}</tbody></table>
<h3>Usage</h3><pre>{html.escape(json.dumps(qa['usage'], indent=2, ensure_ascii=False))}</pre>
</body></html>
"""


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--replay", required=True, type=Path)
    parser.add_argument("--provider", default=None, type=str,
                        help="mock|openai (default: AGENT_PROVIDER env)")
    parser.add_argument("--budget", default=6, type=int)
    parser.add_argument("--report", default="artifacts/council_qa.html", type=Path)
    parser.add_argument("--profile", default=None, type=Path)
    parser.add_argument("--evidence-log", default=None, type=Path)
    parser.add_argument("--audit-log", default=None, type=Path)
    parser.add_argument("--idle-timeout", default=60.0, type=float)
    parser.add_argument("--recompute", action="store_true")
    args = parser.parse_args(argv)
    if args.budget < 4 or args.budget > 32:
        parser.error("--budget must be between 4 and 32")
    return asyncio.run(_run(args))


if __name__ == "__main__":
    sys.exit(main())
