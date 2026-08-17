"""Replay end-to-end at the service layer: the full chain, honest states."""

from __future__ import annotations

import asyncio
from pathlib import Path

from wifi_api.stream import StreamHub, StreamSession
from wifi_council.provider import OpenAIAgentProvider

ROOT = Path(__file__).resolve().parents[2]
WALK = ROOT / "data" / "fixtures" / "walk_through"
DEMO = ROOT / "data" / "fixtures" / "demo_2min"


async def _collect(
    session: StreamSession,
    hub: StreamHub,
    *,
    timeout_s: float = 90.0,
) -> list[dict]:
    hub.attach_session(session)
    session.start()
    deadline = asyncio.get_event_loop().time() + timeout_s
    while not session.status()["finished"] and not session.status()["error"]:
        if asyncio.get_event_loop().time() > deadline:
            raise AssertionError(f"session did not finish: {session.status()}")
        await asyncio.sleep(0.02)
    events = list(hub._buffer)
    if session._event_log_path is not None and session._event_log_path.is_file():
        import json

        with session._event_log_path.open(encoding="utf-8") as handle:
            logged = [
                json.loads(line)
                for line in handle
                if line.strip()
            ]
        if len(logged) > len(events):
            events = logged
    return events


def test_happy_replay_full_chain_on_demo_fixture() -> None:
    """raw -> features -> signals -> evidence -> debate -> policy -> result."""

    async def run() -> dict:
        hub = StreamHub()
        session = StreamSession(
            bundle_root=DEMO,
            paced=False,
            demo_scenario=True,
        )
        events = await _collect(session, hub)
        kinds = {event["event_type"] for event in events}
        claims = [
            claim
            for event in events
            if event["event_type"] == "agent.claim"
            for claim in event["payload"].get("claims", [])
        ]
        challenges = [
            challenge
            for event in events
            if event["event_type"] == "agent.claim"
            for challenge in event["payload"].get("challenges", [])
        ]
        rejections = [
            rejection
            for event in events
            if event["event_type"] == "agent.claim"
            for rejection in event["payload"].get("rejections", [])
        ]
        results = [
            event["payload"]["result"]
            for event in events
            if event["event_type"] == "synthesis.result"
        ]
        return {
            "kinds": kinds,
            "claims": claims,
            "challenges": challenges,
            "rejections": rejections,
            "results": results,
            "status": session.status(),
        }

    outcome = asyncio.run(run())
    kinds = outcome["kinds"]
    for expected in (
        "source.health",
        "signal.frame",
        "quality.update",
        "cycle.started",
        "agent.claim",
        "synthesis.result",
        "session.status",
    ):
        assert expected in kinds, f"missing {expected} in {sorted(kinds)}"
    assert outcome["status"]["windows"] >= 400
    assert outcome["status"]["evidence_seals"] >= 9
    # Demo council behaviors: claims, material challenge, concession,
    # policy rejection, fusion result.
    assert len(outcome["claims"]) >= 4
    assert any(c["proposed_severity"] == "material" for c in outcome["challenges"])
    assert any(
        claim["state"] in ("conceded", "revised")
        for claim in outcome["claims"]
    )
    assert any(
        rejection["reason_code"] == "forbidden_metric_depth"
        for rejection in outcome["rejections"]
    )
    assert outcome["results"]


def test_agent_offline_signals_continue_and_council_unavailable() -> None:
    async def run() -> dict:
        from wifi_council.config import CouncilConfig
        from wifi_council.runtime import CouncilRuntime

        hub = StreamHub()
        runtime = CouncilRuntime(
            CouncilConfig(),
            provider=OpenAIAgentProvider(CouncilConfig(), api_key=None),
        )
        session = StreamSession(
            bundle_root=WALK,
            paced=False,
            council_runtime=runtime,
        )
        events = await _collect(session, hub)
        kinds = {event["event_type"] for event in events}
        results = [
            event["payload"]["result"]
            for event in events
            if event["event_type"] == "synthesis.result"
        ]
        return {"kinds": kinds, "results": results}

    outcome = asyncio.run(run())
    assert "signal.frame" in outcome["kinds"]
    assert outcome["results"]
    assert any(
        result["headline"] == "讨论不可用" for result in outcome["results"]
    )
    assert all(
        result["headline"]
        in ("讨论不可用", "质量门未通过,无推理", "证据封存校验失败")
        for result in outcome["results"]
    )
