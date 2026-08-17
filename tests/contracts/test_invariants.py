"""Hypothesis property tests for the truth-contract invariants."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from hypothesis import given
from hypothesis import strategies as st
from pydantic import ValidationError
from wifi_contracts import (
    AgentActionDecision,
    AgreementSummary,
    CouncilResult,
    DepthProbabilities,
    DepthZone,
    MotionSignal,
    OccupancyDensity,
    OccupancyProbabilities,
    Provenance,
    SignalTriplet,
)

FLOAT = st.floats(
    min_value=0.0,
    max_value=1.0,
    allow_nan=False,
    allow_infinity=False,
)

T0 = datetime(2026, 8, 6, 0, 0, 0, tzinfo=UTC)


def _council_result(
    display_confidence: float,
    model_support: float,
    sensor_confidence_cap: float,
) -> CouncilResult:
    return CouncilResult(
        schema_version="council-result.v1",
        cycle_id="cycle-1",
        evidence_hash="sha256:" + "ab" * 32,
        status="supported",
        headline="baseline",
        summary="deterministic test summary",
        accepted_claim_ids=[],
        unresolved_challenge_ids=[],
        alternatives=[],
        limitations=[],
        sensor_confidence_cap=sensor_confidence_cap,
        model_support=model_support,
        display_confidence=display_confidence,
        interpretation_agreement=AgreementSummary(
            participants=3,
            supporting=3,
            contradicting=0,
            unresolved_challenges=0,
            agreement_ratio=1.0,
        ),
        visual_parameters={},
        audio_parameters={},
        action_decision=AgentActionDecision(
            decision_id="action-cycle-1",
            session_id="session-1",
            cycle_id="cycle-1",
            evidence_hash="sha256:" + "ab" * 32,
            decided_at=T0,
            source_mode="mock",
            quality_status="ok",
            action_type="ambient_light_preview",
            execution_status="simulated_preview",
            target="inference_field_preview",
            reason_code="simulated_source_preview",
            explanation="仅在推断场中模拟环境光反应,不触发外部设备。",
            evidence_refs=[
                f"evidence://sha256:{'ab' * 32}/sensor/sensor_confidence_cap"
            ],
            decision_confidence=min(display_confidence, sensor_confidence_cap),
            sensor_confidence_cap=sensor_confidence_cap,
        ),
        provenance=Provenance(
            contracts_version="1.0.0",
            features_version="features-v1",
            calibration_profile_id="demo_room_v1",
            agent_versions={},
            policy_version="policy-v1",
            generated_at=T0,
        ),
    )


@given(display=FLOAT, model_support=FLOAT, sensor_cap=FLOAT)
def test_council_result_confidence_chain_invariant(
    display: float,
    model_support: float,
    sensor_cap: float,
) -> None:
    if display <= model_support <= sensor_cap:
        result = _council_result(display, model_support, sensor_cap)
        assert (
            0.0
            <= result.display_confidence
            <= result.model_support
            <= result.sensor_confidence_cap
            <= 1.0
        )
    else:
        with pytest.raises(ValidationError):
            _council_result(display, model_support, sensor_cap)


@given(decision=FLOAT, sensor_cap=FLOAT)
def test_agent_action_decision_confidence_never_exceeds_sensor_cap(
    decision: float,
    sensor_cap: float,
) -> None:
    def build() -> AgentActionDecision:
        return AgentActionDecision(
            decision_id="action-cycle-1",
            session_id="session-1",
            cycle_id="cycle-1",
            evidence_hash="sha256:" + "ab" * 32,
            decided_at=T0,
            source_mode="mock",
            quality_status="ok",
            action_type="ambient_light_preview",
            execution_status="simulated_preview",
            target="inference_field_preview",
            reason_code="simulated_source_preview",
            explanation="仅在推断场中模拟环境光反应,不触发外部设备。",
            evidence_refs=[
                f"evidence://sha256:{'ab' * 32}/sensor/sensor_confidence_cap"
            ],
            decision_confidence=decision,
            sensor_confidence_cap=sensor_cap,
        )

    if decision <= sensor_cap:
        assert build().decision_confidence <= sensor_cap
    else:
        with pytest.raises(ValidationError):
            build()


def test_action_confidence_cannot_exceed_council_display_confidence() -> None:
    payload = _council_result(0.4, 0.6, 0.8).model_dump()
    payload["action_decision"]["decision_confidence"] = 0.5

    with pytest.raises(ValidationError):
        CouncilResult.model_validate(payload)


@pytest.mark.parametrize("status", ["ambiguous", "unavailable"])
def test_uncertain_council_result_cannot_expose_simulated_action(
    status: str,
) -> None:
    payload = _council_result(0.4, 0.6, 0.8).model_dump()
    payload["status"] = status

    with pytest.raises(ValidationError):
        CouncilResult.model_validate(payload)


@given(
    a=FLOAT,
    b=FLOAT,
    c=FLOAT,
    d=FLOAT,
)
def test_occupancy_probabilities_must_sum_to_one(
    a: float,
    b: float,
    c: float,
    d: float,
) -> None:
    if abs(a + b + c + d - 1.0) <= 1e-6:
        proxy = OccupancyProbabilities(low=a, medium=b, high=c, unknown=d)
        assert abs(
            proxy.low + proxy.medium + proxy.high + proxy.unknown - 1.0
        ) <= 1e-6
    else:
        with pytest.raises(ValidationError):
            OccupancyProbabilities(low=a, medium=b, high=c, unknown=d)


@given(confidence=FLOAT, cap=FLOAT)
def test_signal_confidence_never_exceeds_cap(confidence: float, cap: float) -> None:
    def build() -> SignalTriplet:
        return SignalTriplet(
            schema_version="1.0.0",
            session_id="session-1",
            window_id="window-1",
            source_mode="mock",
            started_at=T0,
            ended_at=T0 + timedelta(seconds=2),
            motion=MotionSignal(value=0.5, state="idle", confidence=confidence),
            occupancy_density=OccupancyDensity(
                probabilities=OccupancyProbabilities(
                    low=0.25,
                    medium=0.25,
                    high=0.25,
                    unknown=0.25,
                ),
                state="low",
                confidence=confidence,
            ),
            depth_zone=DepthZone(
                probabilities=DepthProbabilities(
                    near=0.25,
                    mid=0.25,
                    far=0.25,
                    unknown=0.25,
                ),
                state="near",
                confidence=confidence,
            ),
            sensor_confidence_cap=cap,
            evidence_refs=[],
            status="ok",
        )

    if confidence <= cap:
        triplet = build()
        assert triplet.motion.confidence <= triplet.sensor_confidence_cap
    else:
        with pytest.raises(ValidationError):
            build()
