"""Role-specific live projections stay deterministic and evidence-bound."""

from __future__ import annotations

from _helpers import make_packet, run_cycle
from wifi_contracts import AgentChallenge, AgentContinuity, AgreementSummary
from wifi_council.presentation import (
    build_skeptic_assessment,
    build_sound_consensus_motion,
    build_specialist_presentation,
)


def continuity(relation: str = "steady") -> AgentContinuity:
    return AgentContinuity(
        relation=relation,  # type: ignore[arg-type]
        changed_signals=[],
        summary="与上一周期对照。",
    )


def test_four_reading_roles_use_their_bounded_state_vocabularies() -> None:
    fast_dense = make_packet(
        motion_state="fast_change",
        motion_value=0.94,
        occupancy_state="high",
        depth_state="near",
    )
    calm_open = make_packet(
        motion_state="idle",
        motion_value=0.05,
        occupancy_state="low",
        depth_state="far",
    )

    architecture = build_specialist_presentation(
        fast_dense, "architecture", continuity()
    )
    biota = build_specialist_presentation(fast_dense, "biota", continuity())
    flow = build_specialist_presentation(fast_dense, "feng_shui", continuity())
    psyche = build_specialist_presentation(fast_dense, "psyche", continuity())
    open_architecture = build_specialist_presentation(
        calm_open, "architecture", continuity()
    )

    assert (architecture.contribution_label, architecture.state_label) == (
        "看见空间的形",
        "收紧",
    )
    assert (biota.contribution_label, biota.state_label) == (
        "看见空间的息",
        "惊跳",
    )
    assert (flow.contribution_label, flow.state_label) == (
        "看见空间的流",
        "冲",
    )
    assert (psyche.contribution_label, psyche.state_label) == (
        "看见空间的势",
        "警觉",
    )
    assert open_architecture.state_label == "展开"
    assert all(
        item.analysis and "房间" in item.analysis
        for item in (architecture, biota)
    )


def test_soundscape_has_no_prose_and_translates_consensus_to_five_axes() -> None:
    packet = make_packet(
        motion_state="fast_change",
        occupancy_state="high",
        depth_state="near",
    )
    presentation = build_specialist_presentation(
        packet, "soundscape", continuity()
    )
    motion = build_sound_consensus_motion(
        packet,
        AgreementSummary(
            participants=5,
            supporting=4,
            contradicting=0,
            unresolved_challenges=0,
            agreement_ratio=0.8,
        ),
        status="supported",
    )

    assert presentation.analysis is None
    assert presentation.contribution == "consensus_motion"
    assert motion.model_dump(exclude={"schema_version"}) == {
        "rhythm": "急拍",
        "pitch": "高",
        "distance": "近",
        "thickness": "厚",
        "synchrony": "同步",
    }


def test_skeptic_exposes_sufficiency_pause_and_next_validation() -> None:
    packet = make_packet(quality_flags=["interference_high"])
    challenge = AgentChallenge(
        challenge_id="challenge-test",
        target_claim_id="claim-test",
        challenger_agent_id="agent-skeptic",
        category="confound",
        proposed_severity="material",
        statement="无线干扰仍可能形成相似代理组合。",
        resolution_test="保持拓扑不变并对照下一周期。",
        status="open",
    )

    assessment = build_skeptic_assessment(packet, challenge)

    assert assessment.evidence_label == "证据有限"
    assert assessment.withhold_judgment is True
    assert assessment.next_validation == "保持拓扑不变并对照下一周期。"


def test_mock_cycle_delivers_all_new_projection_contracts_without_changing_confidence() -> None:
    packet = make_packet(cap=0.7)
    detail = run_cycle(packet)

    assert detail.result is not None
    assert len(detail.claims) == 5
    assert all(claim.presentation is not None for claim in detail.claims)
    sound_claim = next(claim for claim in detail.claims if claim.role == "soundscape")
    assert sound_claim.presentation is not None
    assert sound_claim.presentation.analysis is None
    assert all(challenge.assessment is not None for challenge in detail.challenges)
    assert detail.result.sound_motion is not None
    assert detail.result.life_interaction is not None
    assert detail.result.life_interaction.message.startswith("我")
    assert detail.result.display_confidence <= detail.result.sensor_confidence_cap
