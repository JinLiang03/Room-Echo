"""PolicyArbiter: refs, hashes, forbidden language, gates, invariants."""

from __future__ import annotations

import pytest
from _helpers import FIXED_NOW, claim, make_packet
from hypothesis import given, settings
from hypothesis import strategies as st
from wifi_contracts import AgentChallenge
from wifi_council.config import CouncilConfig
from wifi_council.outputs import (
    ProxyMeasurementSummary,
    SpatialLifeReaction,
    SynthesisOutput,
)
from wifi_council.policy import (
    REASON_DEPTH_REQUIRED_UNKNOWN,
    REASON_FABRICATED_NUMBER,
    REASON_FORBIDDEN_HEALTH,
    REASON_FORBIDDEN_METRIC_DEPTH,
    REASON_FORBIDDEN_PERSON_COUNT,
    REASON_FORBIDDEN_POSE,
    REASON_FORBIDDEN_WALL_PRESENCE,
    REASON_HASH_MISMATCH,
    REASON_OCCUPANCY_DEPTH_UNAVAILABLE,
    REASON_UNAVAILABLE_NARRATED,
    REASON_UNKNOWN_MAPPING_KEY,
    REASON_UNKNOWN_REF,
    REASON_UNKNOWN_TARGET,
    PolicyArbiter,
)


def arbiter() -> PolicyArbiter:
    return PolicyArbiter(CouncilConfig())


def reason_codes(packet, claims, challenges=None) -> list[str]:
    verdict = arbiter().arbitrate(
        packet,
        claims,
        challenges or [],
        now=FIXED_NOW,
    )
    return [rejection.reason_code for rejection in verdict.rejections]


def synthesis(packet, **updates) -> SynthesisOutput:
    measurement = ProxyMeasurementSummary.from_packet(packet)
    values = {
        "measurement_summary": measurement,
        "reaction": SpatialLifeReaction.from_measurement(measurement),
        "headline": "受限总结",
        "plain_language": "当前快照只作代理解释",
        "action": "对照下一周期",
        "uncertainty": "只在当前质量条件内成立",
    }
    values.update(updates)
    return SynthesisOutput(**values)


def test_fictional_ref_rejected() -> None:
    packet = make_packet()
    bad = claim(
        packet,
        refs=[f"evidence://{packet.evidence_hash}/signals/motion/nonexistent"],
    )
    assert REASON_UNKNOWN_REF in reason_codes(packet, [bad])


def test_old_hash_rejected() -> None:
    packet = make_packet()
    bad = claim(
        packet,
        refs=[f"evidence://sha256:{'1' * 64}/signals/motion/value"],
    )
    assert REASON_HASH_MISMATCH in reason_codes(packet, [bad])


def test_valid_refs_accepted() -> None:
    packet = make_packet()
    good = claim(packet)
    verdict = arbiter().arbitrate(packet, [good], [], now=FIXED_NOW)
    assert verdict.rejections == []
    assert [item.claim_id for item in verdict.accepted_claims] == [good.claim_id]
    assert verdict.accepted_claims[0].state == "accepted"


@pytest.mark.parametrize(
    "text,expected",
    [
        ("墙后有人,能看到一个人", REASON_FORBIDDEN_WALL_PRESENCE),
        ("发现两个人", REASON_FORBIDDEN_PERSON_COUNT),
        ("距离约 3.2 米", REASON_FORBIDDEN_METRIC_DEPTH),
        ("人体姿态识别", REASON_FORBIDDEN_POSE),
        ("心率检测", REASON_FORBIDDEN_HEALTH),
        ("confidence=0.95 是我编的", REASON_FABRICATED_NUMBER),
    ],
)
def test_forbidden_language_rejected(text: str, expected: str) -> None:
    packet = make_packet()
    bad = claim(packet, proposition=text)
    assert expected in reason_codes(packet, [bad])


def test_single_rx_depth_claim_rejected() -> None:
    packet = make_packet(depth_allowed=False, depth_state="unknown")
    depth_claim = claim(
        packet,
        role="feng_shui",
        proposition="纵深为 near",
        refs=[f"evidence://{packet.evidence_hash}/signals/depth/state"],
    )
    assert REASON_DEPTH_REQUIRED_UNKNOWN in reason_codes(packet, [depth_claim])


def test_uncalibrated_occupancy_claim_rejected() -> None:
    packet = make_packet(status="uncalibrated", cap=0.0)
    occupancy_claim = claim(
        packet,
        role="biota",
        proposition="占用代理为 high",
        refs=[f"evidence://{packet.evidence_hash}/signals/occupancy/state"],
    )
    codes = reason_codes(packet, [occupancy_claim])
    assert REASON_OCCUPANCY_DEPTH_UNAVAILABLE in codes
    assert REASON_UNAVAILABLE_NARRATED in codes


def test_unavailable_cannot_narrate_presence() -> None:
    packet = make_packet(status="insufficient_signal", cap=0.0)
    motion_claim = claim(packet, proposition="有人在动")
    assert REASON_UNAVAILABLE_NARRATED in reason_codes(packet, [motion_claim])


def test_challenge_severity_confirmed_deterministically() -> None:
    packet = make_packet()
    target = claim(packet)
    info_confound = AgentChallenge(
        schema_version="agent-challenge.v1",
        challenge_id="challenge-1",
        target_claim_id=target.claim_id,
        challenger_agent_id="agent-red-team",
        category="confound",
        proposed_severity="info",
        statement="环境静态变化可能贡献低频扰动。",
        evidence_refs=[f"evidence://{packet.evidence_hash}/quality/packet_coverage"],
        resolution_test="重放对照实验。",
        status="open",
    )
    verdict = arbiter().arbitrate(packet, [target], [info_confound], now=FIXED_NOW)
    assert verdict.challenges[0].proposed_severity == "material"
    assert verdict.status == "ambiguous"
    assert verdict.display_confidence <= verdict.model_support


def test_challenge_with_invalid_ref_rejected_by_policy() -> None:
    packet = make_packet()
    target = claim(packet)
    bad_challenge = AgentChallenge(
        schema_version="agent-challenge.v1",
        challenge_id="challenge-bad",
        target_claim_id=target.claim_id,
        challenger_agent_id="agent-red-team",
        category="confound",
        proposed_severity="material",
        statement="存在未知干扰。",
        evidence_refs=[f"evidence://{packet.evidence_hash}/quality/no_such_path"],
        resolution_test="对照实验。",
        status="open",
    )
    verdict = arbiter().arbitrate(packet, [target], [bad_challenge], now=FIXED_NOW)
    assert verdict.challenges[0].status == "rejected_by_policy"
    assert REASON_UNKNOWN_REF in [r.reason_code for r in verdict.rejections]


def test_challenge_unknown_target_rejected() -> None:
    packet = make_packet()
    ghost = AgentChallenge(
        schema_version="agent-challenge.v1",
        challenge_id="challenge-ghost",
        target_claim_id="claim-ghost",
        challenger_agent_id="agent-red-team",
        category="confound",
        proposed_severity="material",
        statement="目标主张不存在。",
        evidence_refs=[],
        resolution_test="对照实验。",
        status="open",
    )
    verdict = arbiter().arbitrate(packet, [], [ghost], now=FIXED_NOW)
    assert REASON_UNKNOWN_TARGET in [r.reason_code for r in verdict.rejections]


def test_synthesis_unavailable_narration_rejected() -> None:
    packet = make_packet(status="insufficient_signal", cap=0.0)
    verdict = arbiter().arbitrate(packet, [], [], now=FIXED_NOW)
    bad = synthesis(
        packet,
        headline="有人在动",
        plain_language="检测到 moving 状态",
    )
    rejections = arbiter().validate_synthesis(packet, bad, verdict, now=FIXED_NOW)
    assert REASON_UNAVAILABLE_NARRATED in [r.reason_code for r in rejections]


def test_synthesis_unknown_mapping_key_rejected() -> None:
    packet = make_packet()
    verdict = arbiter().arbitrate(packet, [], [], now=FIXED_NOW)
    bad = synthesis(
        packet,
        headline="ok",
        plain_language="ok",
        visual_parameters={"new_number_key": "1.0"},
    )
    rejections = arbiter().validate_synthesis(packet, bad, verdict, now=FIXED_NOW)
    assert REASON_UNKNOWN_MAPPING_KEY in [r.reason_code for r in rejections]


@given(
    cap=st.floats(min_value=0.0, max_value=1.0, allow_nan=False),
    motion_value=st.floats(min_value=0.0, max_value=1.0, allow_nan=False),
)
@settings(max_examples=30, deadline=None)
def test_confidence_chain_property(cap: float, motion_value: float) -> None:
    """For arbitrary caps, display <= model_support <= evidence_ceiling holds."""
    packet = make_packet(
        cap=round(cap, 4),
        motion_value=round(motion_value, 4),
    )
    verdict = arbiter().arbitrate(packet, [], [], now=FIXED_NOW)
    assert 0.0 <= verdict.display_confidence <= verdict.model_support
    assert verdict.model_support <= verdict.evidence_ceiling <= 1.0
