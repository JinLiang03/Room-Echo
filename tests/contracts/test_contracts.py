"""Contract tests: fixture validity, schema views, rejection, and round-trips."""

from __future__ import annotations

import json
from pathlib import Path

import jsonschema
import pytest
from pydantic import BaseModel, ValidationError
from wifi_contracts import (
    CONTRACT_SCHEMAS,
    AgentChallenge,
    AgentClaim,
    CouncilCycleDetail,
    CouncilResult,
    EvidencePacket,
    FeatureWindow,
    NormalizedCsiFrame,
    PolicyRejection,
    SignalTriplet,
    WebSocketEnvelope,
    schema_for,
)

ROOT = Path(__file__).resolve().parents[2]
FIXTURES_DIR = ROOT / "data" / "fixtures"
SCHEMAS_DIR = ROOT / "schemas"

MODEL_BY_FILE: dict[str, type[BaseModel]] = {
    "csi_frames.json": NormalizedCsiFrame,
    "feature_windows.json": FeatureWindow,
    "signal_triplets.json": SignalTriplet,
    "evidence_packets.json": EvidencePacket,
    "agent_claims.json": AgentClaim,
    "agent_challenges.json": AgentChallenge,
    "policy_rejections.json": PolicyRejection,
    "council_results.json": CouncilResult,
    "council_cycle_details.json": CouncilCycleDetail,
}


def _load(filename: str) -> list[dict]:
    return json.loads((FIXTURES_DIR / filename).read_text(encoding="utf-8"))


def _source_mode_of(record: dict) -> str | None:
    if "source_mode" in record:
        return record["source_mode"]
    if "source_manifest" in record:
        return record["source_manifest"]["source_mode"]
    return None


@pytest.mark.parametrize("filename,model", MODEL_BY_FILE.items())
def test_fixtures_validate_as_models(filename: str, model: type[BaseModel]) -> None:
    for record in _load(filename):
        parsed = model.model_validate(record)
        assert parsed.model_dump(mode="json")["schema_version"] in {
            "1.0.0",
            "wifi-evidence.v1",
            "agent-claim.v1",
            "agent-challenge.v1",
            "policy-rejection.v1",
            "council-result.v1",
            "council-cycle.v1",
        }


@pytest.mark.parametrize("filename", MODEL_BY_FILE)
def test_fixtures_are_mock_sourced(filename: str) -> None:
    for record in _load(filename):
        mode = _source_mode_of(record)
        if mode is not None:
            assert mode == "mock"


def _json_validator(schema_file: str) -> jsonschema.Draft202012Validator:
    schema = json.loads((SCHEMAS_DIR / schema_file).read_text(encoding="utf-8"))
    return jsonschema.Draft202012Validator(schema)


def test_csi_frames_pass_checked_in_json_schema() -> None:
    validator = _json_validator("csi_frame.schema.json")
    for record in _load("csi_frames.json"):
        validator.validate(record)


def test_signal_triplets_pass_checked_in_json_schema() -> None:
    validator = _json_validator("signal_triplet.schema.json")
    for record in _load("signal_triplets.json"):
        validator.validate(record)


def test_all_contract_schemas_have_object_type_and_id() -> None:
    for name, _model in CONTRACT_SCHEMAS:
        schema = schema_for(name)
        assert schema["type"] == "object"
        assert schema["$id"].endswith(f"{name}.schema.json")


def test_agent_claim_schema_exports_analysis_steps() -> None:
    claim_schema = schema_for("agent_claim")
    assert "analysis_steps" in claim_schema["properties"]
    step_def = claim_schema["$defs"]["AnalysisStep"]
    assert step_def["properties"]["phase"]["enum"] == [
        "observe",
        "retrieve",
        "map",
        "reason",
        "challenge",
        "conclude",
    ]
    for record in _load("agent_claims.json"):
        claim = AgentClaim.model_validate(record)
        for step in claim.analysis_steps:
            assert step.step_id
            assert step.title
            assert step.text


def test_agent_claim_schema_exports_systematic_reading() -> None:
    claim_schema = schema_for("agent_claim")
    reading_def = claim_schema["$defs"]["SystematicReading"]
    assert set(reading_def["properties"]) == {
        "headline",
        "scene_sketch",
        "layers",
        "narrative",
        "boundary_notes",
        "multimodal_hints",
    }
    layer_def = claim_schema["$defs"]["ReadingLayer"]
    assert layer_def["properties"]["signal"]["enum"] == [
        "motion",
        "occupancy",
        "depth",
    ]
    for record in _load("agent_claims.json"):
        claim = AgentClaim.model_validate(record)
        reading = claim.systematic_reading
        if reading is not None:
            assert reading.headline
            assert len(reading.layers) == 3
            assert reading.narrative


def test_missing_field_rejected() -> None:
    record = _load("csi_frames.json")[0]
    del record["session_id"]
    with pytest.raises(ValidationError):
        NormalizedCsiFrame.model_validate(record)


def test_extra_field_rejected() -> None:
    record = _load("signal_triplets.json")[0]
    record["extra_field"] = True
    with pytest.raises(ValidationError):
        SignalTriplet.model_validate(record)


def test_unknown_source_mode_rejected() -> None:
    record = _load("csi_frames.json")[0]
    record["source_mode"] = "camera"
    with pytest.raises(ValidationError):
        NormalizedCsiFrame.model_validate(record)


def test_probability_sum_must_be_one() -> None:
    record = _load("signal_triplets.json")[0]
    record["occupancy_density"]["probabilities"]["low"] = 0.5
    with pytest.raises(ValidationError):
        SignalTriplet.model_validate(record)


def test_unknown_state_requires_unknown_probability_one() -> None:
    record = _load("signal_triplets.json")[2]
    record["occupancy_density"]["probabilities"]["unknown"] = 0.9
    record["occupancy_density"]["probabilities"]["low"] = 0.1
    with pytest.raises(ValidationError):
        SignalTriplet.model_validate(record)


def test_signal_confidence_cannot_exceed_cap() -> None:
    record = _load("signal_triplets.json")[0]
    record["sensor_confidence_cap"] = 0.1
    with pytest.raises(ValidationError):
        SignalTriplet.model_validate(record)


@pytest.mark.parametrize("filename,model", MODEL_BY_FILE.items())
def test_fixture_json_round_trip_is_stable(filename: str, model: type[BaseModel]) -> None:
    for record in _load(filename):
        parsed = model.model_validate(record)
        first = parsed.model_dump_json()
        reparsed = model.model_validate_json(first)
        assert reparsed.model_dump_json() == first


def test_evidence_hash_seals_the_payload() -> None:
    packet = EvidencePacket.model_validate(_load("evidence_packets.json")[0])
    assert packet.verify_integrity()
    tampered = packet.model_copy(update={"sequence": 999})
    assert not tampered.verify_integrity()


def test_web_socket_envelope_rejects_unknown_event_type() -> None:
    envelope = {
        "schema_version": "ws-event.v1",
        "session_id": "session-1",
        "sequence": 1,
        "emitted_at": "2026-08-06T00:00:00Z",
        "event_type": "signal.frame",
        "payload": {},
    }
    assert WebSocketEnvelope.model_validate(envelope).event_type == "signal.frame"
    envelope["event_type"] = "teleport.invoked"
    with pytest.raises(ValidationError):
        WebSocketEnvelope.model_validate(envelope)
