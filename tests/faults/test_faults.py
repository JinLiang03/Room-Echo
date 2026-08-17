"""Fault injection: packet loss, single RX, TX stale, profile, LLM, disk."""

from __future__ import annotations

import asyncio
from pathlib import Path

from wifi_api.stream import StreamHub, StreamSession

ROOT = Path(__file__).resolve().parents[2]
BUNDLE = ROOT / "data" / "fixtures" / "walk_through"


async def _collect(
    session: StreamSession,
    hub: StreamHub,
    *,
    timeout_s: float = 60.0,
) -> tuple[list[dict], list[dict]]:
    """Run to completion and return (events, triplets)."""
    hub.attach_session(session)
    session.start()
    deadline = asyncio.get_event_loop().time() + timeout_s
    while not session.status()["finished"] and not session.status()["error"]:
        if asyncio.get_event_loop().time() > deadline:
            raise AssertionError("session did not finish")
        await asyncio.sleep(0.02)
    events = list(hub._buffer)
    triplets = [
        event["payload"]["triplet"]
        for event in events
        if event["event_type"] == "signal.frame"
    ]
    return events, triplets


def test_packet_loss_degrades_within_two_windows() -> None:
    async def run() -> list[dict]:
        hub = StreamHub()
        session = StreamSession(bundle_root=BUNDLE, paced=False)
        hub.attach_session(session)
        session.activate_fault("packet_loss", {"ratio": 0.4})
        _events, triplets = await _collect(session, hub)
        return triplets

    triplets = asyncio.run(run())
    degraded = [
        index
        for index, triplet in enumerate(triplets)
        if triplet["status"] in ("degraded", "insufficient_signal")
    ]
    assert degraded, "40% loss must degrade the stream"
    assert degraded[0] <= 2, "degradation must appear within two windows"


def test_single_rx_keeps_motion_and_unknowns_depth() -> None:
    async def run() -> list[dict]:
        hub = StreamHub()
        session = StreamSession(bundle_root=BUNDLE, paced=False)
        hub.attach_session(session)
        session.activate_fault("single_rx", {"keep_link": "rx-a"})
        _events, triplets = await _collect(session, hub)
        return triplets

    triplets = asyncio.run(run())
    assert any(t["motion"]["state"] != "unknown" for t in triplets)
    later = [t for t in triplets[2:] if t["depth_zone"]["state"] == "unknown"]
    assert later, "single RX must set depth unknown"


def test_tx_stale_pauses_and_clears_state() -> None:
    async def run() -> dict:
        hub = StreamHub()
        session = StreamSession(bundle_root=BUNDLE, paced=False)
        hub.attach_session(session)
        session.start()
        await asyncio.sleep(0.4)
        session.activate_fault("tx_stale")
        await asyncio.sleep(0.05)
        assert session.status()["paused"] is True
        frames_before = session.status()["frames"]
        await asyncio.sleep(0.3)
        assert session.status()["frames"] == frames_before
        status = session.status()
        await session.stop()
        return status

    status = asyncio.run(run())
    assert status["paused"] is True


def test_profile_mismatch_makes_occupancy_depth_unavailable() -> None:
    async def run() -> list[dict]:
        hub = StreamHub()
        session = StreamSession(bundle_root=BUNDLE, paced=False)
        hub.attach_session(session)
        session.activate_fault("profile_mismatch")
        _events, triplets = await _collect(session, hub)
        return triplets

    triplets = asyncio.run(run())
    uncalibrated = [
        t
        for t in triplets
        if t["status"] == "uncalibrated"
        and t["occupancy_density"]["state"] == "unknown"
        and t["depth_zone"]["state"] == "unknown"
    ]
    assert uncalibrated, "profile mismatch must make occupancy/depth unavailable"


def test_llm_timeout_yields_deadline_baseline() -> None:
    from wifi_council.config import CouncilConfig

    async def run() -> list[dict]:
        hub = StreamHub()
        session = StreamSession(
            bundle_root=BUNDLE,
            paced=False,
            council_config=CouncilConfig(
                agent_timeout_s=0.2,
                retry_attempts=1,
                cycle_deadline_s=0.3,
            ),
        )
        hub.attach_session(session)
        session.activate_fault("llm_timeout")
        events, _triplets = await _collect(session, hub)
        results = [
            event["payload"]["result"]
            for event in events
            if event["event_type"] == "synthesis.result"
        ]
        return results

    results = asyncio.run(run())
    assert results
    assert any(result["headline"] == "讨论超时" for result in results)


def test_invalid_json_fault_produces_policy_rejection() -> None:
    async def run() -> list[dict]:
        hub = StreamHub()
        session = StreamSession(bundle_root=BUNDLE, paced=False)
        hub.attach_session(session)
        session.activate_fault("invalid_json")
        events, _triplets = await _collect(session, hub)
        rejections = [
            rejection
            for event in events
            if event["event_type"] == "agent.claim"
            for rejection in event["payload"].get("rejections", [])
        ]
        return rejections

    rejections = asyncio.run(run())
    assert rejections, "invalid_json fault must produce policy rejections"
    assert any(
        rejection["reason_code"] == "forbidden_wall_presence"
        for rejection in rejections
    )


def test_disk_error_emits_alert() -> None:
    async def run() -> list[dict]:
        hub = StreamHub()
        session = StreamSession(bundle_root=BUNDLE, paced=False)
        hub.attach_session(session)
        session.activate_fault("disk_error")
        events, _ = await _collect(session, hub)
        return events

    events = asyncio.run(run())
    assert any(
        event["event_type"] == "alert"
        and "disk write error" in event["payload"]["message"]
        for event in events
    )


def test_ws_event_sequences_are_monotonic() -> None:
    async def run() -> list[int]:
        hub = StreamHub()
        session = StreamSession(bundle_root=BUNDLE, paced=False)
        events, _ = await _collect(session, hub)
        return [event["sequence"] for event in events]

    sequences = asyncio.run(run())
    assert sequences == sorted(sequences)
    assert len(set(sequences)) == len(sequences)
