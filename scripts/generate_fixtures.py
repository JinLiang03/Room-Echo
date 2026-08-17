#!/usr/bin/env python3
"""Generate deterministic mock fixtures (fixed seed, source_mode=mock)."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

from wifi_collector.mock_source import MockFrameSource
from wifi_collector.raw_writer import RawBundleWriter
from wifi_collector.replay_bundle import ReplayManifest
from wifi_collector.wire_conversion import wire_bytes_from_normalized
from wifi_contracts import CONTRACTS_VERSION
from wifi_contracts.mock_fixtures import (
    BASE_TIME,
    SEED,
    build_agent_challenges,
    build_agent_claims,
    build_council_cycle_details,
    build_council_results,
    build_evidence_packets,
    build_frames,
    build_policy_rejections,
    build_triplets,
    build_windows,
)

ROOT = Path(__file__).resolve().parents[1]
FIXTURES_DIR = ROOT / "data" / "fixtures"
REPLAY_FIXTURE_DIR = FIXTURES_DIR / "walk_through"
DEMO_FIXTURE_DIR = FIXTURES_DIR / "demo_2min"
REPLAY_FIXTURE_FILES = (
    "manifest.json",
    "raw.csi.zst",
    "events.jsonl",
    "checksums.sha256",
)
REPLAY_SESSION_ID = "session-fixture-walk-through"
DEMO_SESSION_ID = "session-fixture-demo-2min"


def _fake_hash(label: str) -> str:
    import hashlib

    return "sha256:" + hashlib.sha256(label.encode("utf-8")).hexdigest()


async def _build_replay_bundle(
    staging_root: Path,
    *,
    scenario: str,
    recording_id: str,
    session_id: str,
    duration_s: float,
) -> None:
    """Record the mock walk_through scenario as a deterministic bundle."""
    source = MockFrameSource(
        scenario=scenario,
        seed=SEED,
        rate_hz=100,
        duration_s=duration_s,
        session_id=session_id,
        real_time=False,
        started_at=BASE_TIME,
    )
    manifest_src = await source.open()
    manifest = ReplayManifest(
        schema_version="replay-manifest.v1",
        recording_id=recording_id,
        session_id=session_id,
        created_at=BASE_TIME,
        source_mode="mock",
        firmware_version="0.0.0-mock",
        collector_version="0.1.0",
        contracts_version=CONTRACTS_VERSION,
        features_version=None,
        estimator_version=None,
        board_hashes={
            link: _fake_hash(f"board-{link}")
            for link in manifest_src.link_ids
        },
        topology_hash=_fake_hash("topology-two-rx-mock"),
        calibration_profile_id="demo_room_v1",
        channel=6,
        bandwidth_mhz=20,
        files=[],
        ground_truth_present=False,
        privacy="mock fixture; no real MACs, no identity",
        status="incomplete",
    )
    writer = RawBundleWriter(
        session_id=recording_id,
        raw_root=staging_root,
        manifest=manifest,
        clock=lambda: BASE_TIME,
    )
    writer.start()
    writer.append_event("session.started", {"source_mode": "mock"})
    count = 0
    async for frame in source.frames():
        writer.append_wire_frame(wire_bytes_from_normalized(frame))
        count += 1
    writer.append_event(
        "session.stopped",
        {"frames_recorded": count},
    )
    writer.finalize()


def build_replay_fixture_to(staging_root: Path) -> None:
    asyncio.run(
        _build_replay_bundle(
            staging_root,
            scenario="walk_through",
            recording_id="walk_through",
            session_id=REPLAY_SESSION_ID,
            duration_s=10.0,
        )
    )
    asyncio.run(
        _build_replay_bundle(
            staging_root,
            scenario="demo_2min",
            recording_id="demo_2min",
            session_id=DEMO_SESSION_ID,
            duration_s=120.0,
        )
    )


def _replay_fixture_matches(staging: Path) -> list[str]:
    drifted: list[str] = []
    for bundle_id, committed_dir in (
        ("walk_through", REPLAY_FIXTURE_DIR),
        ("demo_2min", DEMO_FIXTURE_DIR),
    ):
        for name in REPLAY_FIXTURE_FILES:
            generated = staging / bundle_id / name
            committed = committed_dir / name
            if not generated.is_file() or not committed.is_file():
                drifted.append(str(committed))
                continue
            if generated.read_bytes() != committed.read_bytes():
                drifted.append(str(committed))
    return drifted


def payloads() -> dict[str, list[object]]:
    return {
        "csi_frames.json": build_frames(),
        "feature_windows.json": build_windows(),
        "signal_triplets.json": build_triplets(),
        "evidence_packets.json": build_evidence_packets(),
        "agent_claims.json": build_agent_claims(),
        "agent_challenges.json": build_agent_challenges(),
        "policy_rejections.json": build_policy_rejections(),
        "council_results.json": build_council_results(),
        "council_cycle_details.json": build_council_cycle_details(),
    }


def write_fixtures(check: bool) -> int:
    drifted: list[str] = []
    for filename, objects in payloads().items():
        data = [obj.model_dump(mode="json") for obj in objects]
        rendered = json.dumps(data, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
        path = FIXTURES_DIR / filename
        if check:
            if not path.is_file() or path.read_text(encoding="utf-8") != rendered:
                drifted.append(str(path))
        else:
            path.write_text(rendered, encoding="utf-8")

    staging_root = Path(tempfile.mkdtemp(prefix="wsc-replay-staging-", dir=FIXTURES_DIR))
    try:
        build_replay_fixture_to(staging_root)
        if check:
            drifted.extend(_replay_fixture_matches(staging_root))
        else:
            for bundle_id, committed_dir in (
                ("walk_through", REPLAY_FIXTURE_DIR),
                ("demo_2min", DEMO_FIXTURE_DIR),
            ):
                if committed_dir.exists():
                    shutil.rmtree(committed_dir)
                os.replace(staging_root / bundle_id, committed_dir)
    finally:
        shutil.rmtree(staging_root, ignore_errors=True)

    if check and drifted:
        print("Fixture drift detected:")
        for path in drifted:
            print(f"- {path}")
        return 1
    action = "Verified" if check else "Wrote"
    print(f"{action} deterministic fixtures in {FIXTURES_DIR} (seed={SEED:#x})")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="fail on drift without writing")
    args = parser.parse_args()
    return write_fixtures(check=args.check)


if __name__ == "__main__":
    sys.exit(main())
