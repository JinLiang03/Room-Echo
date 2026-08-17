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
    # The skeptic targets one current claim and that interpreter responds
    # within the bounded call budget.
    assert detail.challenges
    assert detail.challenges[0].category == "confound"
    assert all(challenge.status == "resolved" for challenge in detail.challenges)
    target_id = detail.challenges[0].target_claim_id
    assert any(
        claim.claim_id == target_id and claim.state == "revised"
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
    assert call.value.scene_decision == "unknown"
    assert "保持未知" in call.value.render_proposition()


def test_skeptic_targets_one_current_claim_and_current_snapshot() -> None:
    packet = make_packet()
    detail = run_cycle(packet)
    assert detail.challenges
    challenge = detail.challenges[0]
    target = next(
        claim for claim in detail.claims if claim.claim_id == challenge.target_claim_id
    )
    assert "视角" in challenge.statement
    assert target.claim_id not in challenge.statement
    assert "活动=持续变化" in challenge.statement
    assert "占用=低" in challenge.statement
    assert "相对纵深=偏近" in challenge.statement
    for path in (
        "signals/motion/state",
        "signals/occupancy/state",
        "signals/depth/state",
        "quality/overall_status",
    ):
        assert any(ref.endswith(f"/{path}") for ref in challenge.evidence_refs)
    assert "下一周期" in challenge.resolution_test


def test_fusion_gives_one_grounded_action_with_a_boundary() -> None:
    detail = run_cycle(make_packet())
    assert detail.result is not None
    summary = detail.result.summary
    assert summary.startswith(
        "代理数据:活动=moving,占用=low,相对纵深=near,质量=ok"
    )
    assert "空间生命体反应(叙事隐喻,不表示真实生命或意识)" in summary
    assert "建议:" in summary
    assert "限制:" in summary


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
