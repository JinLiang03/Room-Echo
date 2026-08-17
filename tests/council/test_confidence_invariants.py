"""Confidence invariants: agent count/agreement/duplicates never inflate."""

from __future__ import annotations

import asyncio

from _helpers import FIXED_NOW, make_packet, run_cycle
from wifi_council.audit import CouncilStore
from wifi_council.config import CouncilConfig
from wifi_council.orchestrator import CouncilOrchestrator
from wifi_council.provider import MockAgentProvider


def _display(packet, roles) -> float:
    detail = run_cycle(packet, roles=roles)
    assert detail.result is not None
    return detail.result.display_confidence


def test_agent_count_does_not_change_confidence() -> None:
    packet = make_packet(cap=0.6)
    one = _display(packet, ("feng_shui",))
    three = _display(packet, ("architecture", "biota", "feng_shui"))
    five = _display(packet, None)
    assert one == three == five == 0.6


def test_agreement_does_not_inflate_confidence() -> None:
    """Challenge/disagreement never raises the sensor-bound display."""
    calm = make_packet(cap=0.5)
    contested = make_packet(cap=0.5, quality_flags=["interference_high"])
    calm_detail = run_cycle(calm)
    contested_detail = run_cycle(contested)
    assert calm_detail.result is not None and contested_detail.result is not None
    assert calm_detail.result.interpretation_agreement.supporting == 5
    assert any(
        challenge.proposed_severity == "material"
        for challenge in contested_detail.challenges
    )
    assert (
        calm_detail.result.display_confidence
        == contested_detail.result.display_confidence
        == 0.5
    )


def test_duplicate_evidence_does_not_increase_display() -> None:
    packet = make_packet(cap=0.5)
    config = CouncilConfig(max_calls_per_cycle=8)
    orchestrator = CouncilOrchestrator(MockAgentProvider(config), config)
    detail = asyncio.run(orchestrator.run_cycle(packet, now=FIXED_NOW))
    assert detail.result is not None
    display = detail.result.display_confidence
    for _ in range(9):
        again = asyncio.run(orchestrator.run_cycle(packet, now=FIXED_NOW))
        assert again.result is not None
        assert again.result.display_confidence == display == 0.5
    # The store refuses the same sealed cycle twice; duplicates never re-raise.
    store = CouncilStore()
    assert store.commit(detail, packet.sequence) is True
    assert store.commit(detail, packet.sequence) is False
    assert store.current is not None
    assert store.current.result is not None
    assert store.current.result.display_confidence == 0.5


def test_unknown_signals_yield_zero_display() -> None:
    packet = make_packet(
        motion_state="unknown",
        occupancy_state="unknown",
        depth_state="unknown",
        status="insufficient_signal",
        cap=0.0,
    )
    detail = run_cycle(packet)
    assert detail.result is not None
    assert detail.result.status == "unavailable"
    assert detail.result.display_confidence == 0.0
    assert detail.result.model_support == 0.0


def test_fusion_numbers_trace_to_approved_input() -> None:
    packet = make_packet(cap=0.7)
    detail = run_cycle(packet)
    result = detail.result
    assert result is not None
    # Every numeric output equals the sealed sensor values verbatim.
    assert result.sensor_confidence_cap == packet.signals.sensor_confidence_cap == 0.7
    assert result.model_support == min(
        packet.signals.motion.confidence,
        packet.signals.occupancy_density.confidence,
        packet.signals.depth_zone.confidence,
    )
    assert result.display_confidence == result.model_support
    assert set(result.visual_parameters) == {"palette", "shape"}
    assert set(result.audio_parameters) == {"enabled", "tone"}
    assert result.accepted_claim_ids
    assert result.evidence_hash == packet.evidence_hash
    assert result.provenance.models
