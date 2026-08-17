"""Mock council debate: full snapshot, confounds, abstains, bad outputs."""

from __future__ import annotations

import asyncio
import json

from _helpers import make_packet, run_cycle
from wifi_council.config import CouncilConfig
from wifi_council.prompts import build_prompt
from wifi_council.provider import MockAgentProvider


def test_full_debate_snapshot() -> None:
    packet = make_packet()
    detail = run_cycle(packet)
    assert detail.phase == "commit"
    assert detail.status == "supported"
    assert [claim.role for claim in detail.claims] == [
        "architecture",
        "biota",
        "feng_shui",
        "psyche",
        "soundscape",
    ]
    # The skeptic cross-examined the first non-abstain claim and the
    # interpreter responded (revised) within the call budget.
    assert detail.challenges
    assert detail.challenges[0].category == "confound"
    assert all(challenge.status == "resolved" for challenge in detail.challenges)
    assert any(
        claim.role == "architecture" and claim.state == "revised"
        for claim in detail.claims
    )
    phases = [record.phase for record in detail.calls]
    assert phases.count("propose") == 5
    assert "cross_examine" in phases
    assert "respond" in phases
    assert "synthesize" in phases
    result = detail.result
    assert result is not None
    assert result.display_confidence == result.model_support == 0.8
    assert result.sensor_confidence_cap == 0.8


def test_debate_is_deterministic() -> None:
    packet = make_packet()
    first = run_cycle(packet)
    second = run_cycle(packet)
    assert first.result is not None and second.result is not None
    assert first.result.model_dump_json() == second.result.model_dump_json()
    assert [
        (claim.role, claim.stance, claim.state, claim.proposition)
        for claim in first.claims
    ] == [
        (claim.role, claim.stance, claim.state, claim.proposition)
        for claim in second.claims
    ]
    assert [
        (challenge.category, challenge.proposed_severity, challenge.status)
        for challenge in first.challenges
    ] == [
        (challenge.category, challenge.proposed_severity, challenge.status)
        for challenge in second.challenges
    ]


def test_interference_scenario_has_material_confound() -> None:
    packet = make_packet(quality_flags=["interference_high"])
    detail = run_cycle(packet)
    motion_challenges = [
        challenge
        for challenge in detail.challenges
        if challenge.proposed_severity == "material"
        and any(
            claim.role == "feng_shui" and claim.claim_id == challenge.target_claim_id
            for claim in detail.claims
        )
    ]
    assert motion_challenges, "interference must produce a material confound"
    assert "干扰" in motion_challenges[0].statement
    # A resolved material challenge still does not inflate confidence.
    result = detail.result
    assert result is not None
    assert result.display_confidence == result.model_support


def test_single_rx_depth_abstains() -> None:
    provider = MockAgentProvider(CouncilConfig())
    packet = make_packet(
        motion_state="unknown",
        occupancy_state="unknown",
        depth_state="unknown",
        status="insufficient_signal",
        cap=0.0,
    )
    call = asyncio.run(provider.propose("feng_shui", packet, build_prompt("feng_shui")))
    assert call.value is not None
    assert call.value.abstain is True
    assert "abstain" in call.value.proposition


def test_misbehavior_bad_refs_is_rejected_by_policy() -> None:
    packet = make_packet()
    detail = run_cycle(packet, misbehave="bad_refs")
    assert any(
        rejection.reason_code == "unknown_evidence_ref"
        for rejection in detail.rejections
    )
    assert any(claim.role == "feng_shui" for claim in detail.claims)


def test_default_budget_caps_calls() -> None:
    packet = make_packet()
    detail = run_cycle(packet, budget=6)
    assert len(detail.calls) <= 6
    phases = [record.phase for record in detail.calls]
    assert phases.count("propose") == 5
    assert "respond" not in phases
    assert "synthesize" not in phases


def test_gate_failure_skips_inference() -> None:
    packet = make_packet(status="insufficient_signal", cap=0.0)
    detail = run_cycle(packet)
    assert detail.calls == []
    assert detail.status == "unavailable"
    assert detail.result is not None
    assert detail.result.headline == "质量门未通过,无推理"


def test_seal_failure_skips_inference() -> None:
    packet = make_packet()
    tampered = packet.model_copy(update={"sequence": 999})
    detail = run_cycle(tampered)
    assert detail.calls == []
    assert detail.status == "unavailable"
    assert "封存校验失败" in (detail.result.headline if detail.result else "")


def test_mock_snapshot_json_is_stable() -> None:
    packet = make_packet()
    detail = run_cycle(packet)
    snapshot = {
        "status": detail.status,
        "claims": [
            [claim.role, claim.stance, claim.state, claim.proposition]
            for claim in detail.claims
        ],
        "challenges": [
            [challenge.category, challenge.proposed_severity, challenge.status]
            for challenge in detail.challenges
        ],
        "result": json.loads(detail.result.model_dump_json()) if detail.result else None,
    }
    again = run_cycle(packet)
    snapshot_again = {
        "status": again.status,
        "claims": [
            [claim.role, claim.stance, claim.state, claim.proposition]
            for claim in again.claims
        ],
        "challenges": [
            [challenge.category, challenge.proposed_severity, challenge.status]
            for challenge in again.challenges
        ],
        "result": json.loads(again.result.model_dump_json()) if again.result else None,
    }
    assert snapshot == snapshot_again
