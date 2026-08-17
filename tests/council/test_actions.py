"""Deterministic action decisions stay evidence-bound and non-executing."""

from __future__ import annotations

import pytest
from _helpers import FIXED_NOW, make_packet
from pydantic import ValidationError
from wifi_contracts import AgentActionDecision, EvidencePacket
from wifi_council.actions import build_agent_action_decision
from wifi_council.config import CouncilConfig
from wifi_council.fusion import FusionAssembler
from wifi_council.outputs import (
    ProxyMeasurementSummary,
    SpatialLifeReaction,
    SynthesisOutput,
)
from wifi_council.policy import PolicyArbiter


def _packet_mode(mode: str) -> EvidencePacket:
    packet = make_packet()
    manifest = packet.source_manifest.model_copy(update={"source_mode": mode})
    signals = packet.signals.model_copy(update={"source_mode": mode})
    return EvidencePacket.create(
        **packet.model_copy(
            update={"source_manifest": manifest, "signals": signals}
        ).model_dump()
    )


@pytest.mark.parametrize("mode", ["mock", "replay"])
def test_supported_simulated_sources_emit_only_a_labelled_ui_preview(mode: str) -> None:
    packet = _packet_mode(mode)
    decision = build_agent_action_decision(
        packet,
        status="supported",
        decision_confidence=0.8,
        decided_at=FIXED_NOW,
    )

    assert decision.action_type == "ambient_light_preview"
    assert decision.execution_status == "simulated_preview"
    assert decision.target == "inference_field_preview"
    assert decision.reason_code == "simulated_source_preview"
    assert decision.source_mode == mode
    assert decision.decision_confidence <= decision.sensor_confidence_cap


def test_live_always_withholds_because_no_actuator_adapter_exists() -> None:
    packet = _packet_mode("live")
    decision = build_agent_action_decision(
        packet,
        status="supported",
        decision_confidence=0.8,
        decided_at=FIXED_NOW,
    )

    assert decision.action_type == "stay_silent"
    assert decision.execution_status == "withheld"
    assert decision.target == "none"
    assert decision.reason_code == "no_actuator_adapter"


@pytest.mark.parametrize(
    ("status", "expected_action", "expected_reason"),
    [
        ("ambiguous", "wait_and_observe", "awaiting_validation"),
        ("unavailable", "stay_silent", "insufficient_evidence"),
    ],
)
def test_uncertain_results_never_emit_a_preview(
    status: str,
    expected_action: str,
    expected_reason: str,
) -> None:
    decision = build_agent_action_decision(
        make_packet(),
        status=status,  # type: ignore[arg-type]
        decision_confidence=0.4,
        decided_at=FIXED_NOW,
    )

    assert decision.action_type == expected_action
    assert decision.execution_status == "withheld"
    assert decision.reason_code == expected_reason
    if status == "unavailable":
        assert decision.decision_confidence == 0.0


def test_tampered_or_cross_source_evidence_fails_closed() -> None:
    packet = make_packet()
    tampered = packet.model_copy(update={"sequence": packet.sequence + 1})
    tampered_decision = build_agent_action_decision(
        tampered,
        status="supported",
        decision_confidence=0.8,
        decided_at=FIXED_NOW,
    )
    assert tampered_decision.reason_code == "evidence_integrity_failed"
    assert tampered_decision.execution_status == "withheld"

    mismatched = EvidencePacket.create(
        **packet.model_copy(
            update={
                "signals": packet.signals.model_copy(update={"source_mode": "replay"})
            }
        ).model_dump()
    )
    mismatch_decision = build_agent_action_decision(
        mismatched,
        status="supported",
        decision_confidence=0.8,
        decided_at=FIXED_NOW,
    )
    assert mismatch_decision.reason_code == "source_contract_mismatch"
    assert mismatch_decision.execution_status == "withheld"


def test_tampered_live_evidence_is_withheld_without_contract_failure() -> None:
    packet = _packet_mode("live")
    tampered = packet.model_copy(update={"sequence": packet.sequence + 1})

    decision = build_agent_action_decision(
        tampered,
        status="supported",
        decision_confidence=0.8,
        decided_at=FIXED_NOW,
    )

    assert decision.source_mode == "live"
    assert decision.execution_status == "withheld"
    assert decision.reason_code == "evidence_integrity_failed"


def _synthesis(packet: EvidencePacket, action: str) -> SynthesisOutput:
    measurement = ProxyMeasurementSummary.from_packet(packet)
    return SynthesisOutput(
        measurement_summary=measurement,
        reaction=SpatialLifeReaction.from_measurement(measurement),
        headline="受限解释",
        plain_language="当前只呈现代理信号形成的抽象变化",
        action=action,
        uncertainty="只在当前质量与标定条件内成立",
    )


def test_provider_free_text_cannot_choose_or_modify_the_action_decision() -> None:
    packet = make_packet()
    config = CouncilConfig()
    verdict = PolicyArbiter(config).arbitrate(packet, [], [], now=FIXED_NOW)
    assembler = FusionAssembler(config)

    first = assembler.assemble(
        packet,
        verdict,
        synthesis=_synthesis(packet, "保存当前候选"),
        features_version="features-v2",
        prompt_version="prompt-a",
        provider_models={"fusion": "provider-a"},
        generated_at=FIXED_NOW,
    )
    second = assembler.assemble(
        packet,
        verdict,
        synthesis=_synthesis(packet, "改用另一段自由文本"),
        features_version="features-v2",
        prompt_version="prompt-b",
        provider_models={"fusion": "provider-b"},
        generated_at=FIXED_NOW,
    )

    assert first.summary != second.summary
    assert first.action_decision == second.action_decision
    assert first.action_decision.action_type == "ambient_light_preview"


@pytest.mark.parametrize(
    "forbidden",
    [
        "night routine",
        "path",
        "fall",
        "person",
        "夜间路径",
        "跌倒",
        "作息",
        "有人",
    ],
)
def test_action_contract_rejects_forbidden_inference_text(forbidden: str) -> None:
    packet = make_packet()
    valid = build_agent_action_decision(
        packet,
        status="supported",
        decision_confidence=0.8,
        decided_at=FIXED_NOW,
    )
    payload = valid.model_dump()
    payload["explanation"] = forbidden

    with pytest.raises(ValidationError):
        AgentActionDecision.model_validate(payload)
