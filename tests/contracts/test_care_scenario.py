"""Truth-boundary tests for the fictional ageing-in-place scenario."""

from __future__ import annotations

import json
from pathlib import Path

import jsonschema
import pytest
from pydantic import ValidationError
from wifi_contracts import (
    CareMomentEvidenceCore,
    CareMomentKey,
    SimulatedCareScenario,
    build_simulated_care_scenario,
    canonical_care_evidence_hash,
)

ROOT = Path(__file__).resolve().parents[2]
MOMENTS: tuple[CareMomentKey, ...] = (
    "routine",
    "bathroom_timeout",
    "fall_drill",
    "pet_night",
)
SUGGESTION_KINDS = {
    "ambient_light_preview",
    "voice_checkin_preview",
    "family_notification_draft",
    "robot_inspection_preview",
}


def _rehash_moment(payload: dict, index: int) -> None:
    """Rebind refs after a deliberate evidence-core mutation in a negative test."""
    moment = payload["moments"][index]
    old_hash = moment["evidence_hash"]
    new_hash = canonical_care_evidence_hash(
        CareMomentEvidenceCore.model_validate(moment["evidence_core"])
    )
    moment["evidence_hash"] = new_hash
    moment["facts"]["evidence_refs"] = [
        ref.replace(old_hash, new_hash)
        for ref in moment["facts"]["evidence_refs"]
    ]
    for suggestion in moment["suggestions"]:
        suggestion["evidence_refs"] = [
            ref.replace(old_hash, new_hash)
            for ref in suggestion["evidence_refs"]
        ]


@pytest.mark.parametrize("selected", MOMENTS)
def test_simulated_care_scenario_selects_a_deterministic_moment(
    selected: CareMomentKey,
) -> None:
    scenario = build_simulated_care_scenario(selected)

    assert scenario.simulation_only is True
    assert scenario.source_mode == "mock"
    assert scenario.device_execution_enabled is False
    assert scenario.resident.contains_real_person_data is False
    assert scenario.home.layout_source == "simulated_fixture_not_sensor_inferred"
    assert scenario.selected_moment == selected
    assert scenario.moments[scenario.current_index].moment == selected
    assert {moment.moment for moment in scenario.moments} == set(MOMENTS)


def test_every_care_moment_has_four_bounded_action_suggestions() -> None:
    scenario = build_simulated_care_scenario()

    for moment in scenario.moments:
        assert len(moment.suggestions) == 4
        assert {suggestion.kind for suggestion in moment.suggestions} == SUGGESTION_KINDS
        for suggestion in moment.suggestions:
            assert suggestion.execution_status in {"simulated_preview", "withheld"}
            assert suggestion.external_execution_allowed is False
            assert suggestion.action_confidence <= moment.conclusion_confidence
            assert (
                suggestion.action_confidence
                <= suggestion.sensor_confidence_cap
                == moment.sensor_confidence_cap
            )
            assert all(
                ref.startswith(f"evidence://{moment.evidence_hash}/")
                for ref in suggestion.evidence_refs
            )
            assert all("/suggestions/" not in ref for ref in suggestion.evidence_refs)


def test_nonexistent_evidence_core_path_is_rejected() -> None:
    payload = build_simulated_care_scenario().model_dump(mode="json")
    moment = payload["moments"][1]
    moment["facts"]["evidence_refs"][0] = (
        f"evidence://{moment['evidence_hash']}/evidence_core/does/not/exist"
    )

    with pytest.raises(ValidationError, match="does not resolve"):
        SimulatedCareScenario.model_validate(payload)


def test_suggestion_cannot_reference_unhashed_suggestion_content() -> None:
    payload = build_simulated_care_scenario().model_dump(mode="json")
    moment = payload["moments"][1]
    moment["suggestions"][0]["evidence_refs"] = [
        f"evidence://{moment['evidence_hash']}/suggestions/ambient_light_preview"
    ]

    with pytest.raises(ValidationError, match="does not resolve"):
        SimulatedCareScenario.model_validate(payload)


def test_checked_in_care_fixture_passes_checked_in_json_schema() -> None:
    fixture = json.loads(
        (ROOT / "data/fixtures/simulated_care_scenarios.json").read_text(
            encoding="utf-8"
        )
    )
    schema = json.loads(
        (ROOT / "schemas/simulated_care_scenario.schema.json").read_text(
            encoding="utf-8"
        )
    )
    validator = jsonschema.Draft202012Validator(schema)

    assert len(fixture) == 1
    validator.validate(fixture[0])


def test_embedded_proxy_triplet_does_not_rebase_local_schema_refs() -> None:
    care_schema = json.loads(
        (ROOT / "schemas/simulated_care_scenario.schema.json").read_text(
            encoding="utf-8"
        )
    )
    signal_schema = json.loads(
        (ROOT / "schemas/signal_triplet.schema.json").read_text(encoding="utf-8")
    )

    # An embedded standalone $id would rebase SignalTriplet's
    # ``#/$defs/DepthZone``-style refs away from the care document, where the
    # shared definitions actually live.  The standalone contract still owns
    # and advertises its canonical id.
    assert "$id" not in care_schema["$defs"]["SignalTriplet"]
    assert signal_schema["$id"].endswith("/signal_triplet.schema.json")


def test_truth_markers_are_required_in_schema_and_generated_types() -> None:
    schema = json.loads(
        (ROOT / "schemas/simulated_care_scenario.schema.json").read_text(
            encoding="utf-8"
        )
    )
    assert {
        "schema_version",
        "simulation_only",
        "source_mode",
        "device_execution_enabled",
    } <= set(schema["required"])
    required_by_definition = {
        "CareMomentEvidenceCore": {"proxy_triplet"},
        "SimulatedResidentProfile": {
            "profile_origin",
            "contains_real_person_data",
        },
        "SimulatedHomeLayout": {"layout_source"},
        "SimulatedExternalObservation": {"simulation_only"},
        "SimulatedCareMoment": {"scenario_only", "interpretation_status"},
        "SimulatedCareSuggestion": {"external_execution_allowed"},
    }
    for definition, required in required_by_definition.items():
        assert required <= set(schema["$defs"][definition]["required"])

    generated_types = (
        ROOT / "apps/web/src/generated/contracts.ts"
    ).read_text(encoding="utf-8")
    assert "simulation_only?: true" not in generated_types
    assert "scenario_only?: true" not in generated_types
    assert "external_execution_allowed?: false" not in generated_types
    assert "contains_real_person_data?: false" not in generated_types
    assert "proxy_triplet?: SignalTriplet" not in generated_types
    assert 'schema_version: "care-evidence-core.v2"' in generated_types
    assert 'schema_version: "simulated-care-scenario.v2"' in generated_types
    assert 'interpretation_status: "supported" | "unknown"' in generated_types


def test_moments_match_timeline_event_zone_time_sources_and_duration() -> None:
    scenario = build_simulated_care_scenario()
    entries = {entry.entry_id: entry for entry in scenario.timeline}

    for moment in scenario.moments:
        entry = entries[moment.timeline_entry_id]
        assert moment.event_id == entry.event_id
        assert moment.facts.zone_id == entry.zone_id
        assert moment.occurred_at == entry.ended_at
        assert moment.facts.input_sources == entry.input_sources
        assert moment.facts.observed_duration_min == (
            entry.ended_at - entry.started_at
        ).total_seconds() / 60


def test_every_moment_has_one_hash_bound_atomic_proxy_triplet() -> None:
    scenario = build_simulated_care_scenario()
    entries = {entry.entry_id: entry for entry in scenario.timeline}
    window_ids: set[str] = set()

    for moment in scenario.moments:
        entry = entries[moment.timeline_entry_id]
        triplet = moment.evidence_core.proxy_triplet
        assert triplet.session_id == scenario.scenario_id
        assert triplet.source_mode == scenario.source_mode == "mock"
        assert triplet.window_id == f"{moment.event_id}-proxy-final"
        assert entry.started_at <= triplet.started_at < triplet.ended_at
        assert triplet.ended_at == moment.occurred_at == entry.ended_at
        assert triplet.sensor_confidence_cap == moment.sensor_confidence_cap
        assert triplet.status == "ok"
        assert triplet.evidence_refs == [
            f"fixture://{scenario.scenario_id}/proxy/{triplet.window_id}"
        ]
        assert triplet.window_id not in window_ids
        window_ids.add(triplet.window_id)
        assert moment.evidence_hash == canonical_care_evidence_hash(
            moment.evidence_core
        )
        assert max(
            triplet.motion.confidence,
            triplet.occupancy_density.confidence,
            triplet.depth_zone.confidence,
        ) <= triplet.sensor_confidence_cap


def test_proxy_triplet_measurement_change_rejects_old_event_hash() -> None:
    payload = build_simulated_care_scenario("bathroom_timeout").model_dump(
        mode="json"
    )
    payload["moments"][1]["evidence_core"]["proxy_triplet"]["motion"][
        "value"
    ] = 0.44

    with pytest.raises(ValidationError, match="canonical evidence core"):
        SimulatedCareScenario.model_validate(payload)


def test_proxy_triplet_from_another_session_is_rejected_after_rehash() -> None:
    payload = build_simulated_care_scenario("bathroom_timeout").model_dump(
        mode="json"
    )
    payload["moments"][1]["evidence_core"]["proxy_triplet"][
        "session_id"
    ] = "another-simulated-session"
    _rehash_moment(payload, 1)

    with pytest.raises(ValidationError, match="proxy triplet session"):
        SimulatedCareScenario.model_validate(payload)


def test_proxy_triplet_outside_bound_timeline_entry_is_rejected_after_rehash() -> None:
    payload = build_simulated_care_scenario("bathroom_timeout").model_dump(
        mode="json"
    )
    payload["moments"][1]["evidence_core"]["proxy_triplet"][
        "started_at"
    ] = "2026-08-13T11:44:59.750000+08:00"
    _rehash_moment(payload, 1)

    with pytest.raises(ValidationError, match="within its timeline entry"):
        SimulatedCareScenario.model_validate(payload)


def test_proxy_triplet_non_mock_source_is_rejected() -> None:
    payload = build_simulated_care_scenario("bathroom_timeout").model_dump(
        mode="json"
    )
    payload["moments"][1]["evidence_core"]["proxy_triplet"][
        "source_mode"
    ] = "replay"

    with pytest.raises(ValidationError, match="source_mode must be mock"):
        SimulatedCareScenario.model_validate(payload)


def test_proxy_triplet_cap_must_match_event_evidence_core() -> None:
    payload = build_simulated_care_scenario("bathroom_timeout").model_dump(
        mode="json"
    )
    payload["moments"][1]["evidence_core"]["proxy_triplet"][
        "sensor_confidence_cap"
    ] = 0.9

    with pytest.raises(ValidationError, match="sensor cap must match"):
        SimulatedCareScenario.model_validate(payload)


def test_proxy_triplet_window_id_must_bind_to_event() -> None:
    payload = build_simulated_care_scenario("bathroom_timeout").model_dump(
        mode="json"
    )
    second_triplet = payload["moments"][1]["evidence_core"]["proxy_triplet"]
    second_triplet["window_id"] = "unbound-care-window"
    second_triplet["evidence_refs"] = [
        f"fixture://{payload['scenario_id']}/proxy/unbound-care-window"
    ]
    with pytest.raises(ValidationError, match="same care event"):
        SimulatedCareScenario.model_validate(payload)


def test_proxy_triplet_fixture_ref_must_match_its_window_after_rehash() -> None:
    payload = build_simulated_care_scenario("bathroom_timeout").model_dump(
        mode="json"
    )
    payload["moments"][1]["evidence_core"]["proxy_triplet"][
        "evidence_refs"
    ] = ["fixture://wrong-scenario/proxy/wrong-window"]
    _rehash_moment(payload, 1)

    with pytest.raises(ValidationError, match="evidence ref"):
        SimulatedCareScenario.model_validate(payload)


def test_unresolved_nested_proxy_evidence_path_is_rejected() -> None:
    payload = build_simulated_care_scenario().model_dump(mode="json")
    moment = payload["moments"][1]
    moment["facts"]["evidence_refs"][0] = (
        f"evidence://{moment['evidence_hash']}/"
        "evidence_core/proxy_triplet/motion/not_a_field"
    )

    with pytest.raises(ValidationError, match="does not resolve"):
        SimulatedCareScenario.model_validate(payload)


@pytest.mark.parametrize(
    "field,replacement,error",
    [
        ("event_id", "wrong-event", "event_id does not match timeline"),
        ("zone_id", "bedroom", "zone does not match timeline"),
        ("ended_at", "2026-08-13T12:44:00+08:00", "occurred_at"),
        ("input_sources", ["simulated_clock"], "sources do not match timeline"),
    ],
)
def test_timeline_mismatch_is_rejected(
    field: str,
    replacement: object,
    error: str,
) -> None:
    payload = build_simulated_care_scenario().model_dump(mode="json")
    payload["timeline"][5][field] = replacement

    with pytest.raises(ValidationError, match=error):
        SimulatedCareScenario.model_validate(payload)


def test_plain_language_events_expose_duration_threshold_inputs_and_unknowns() -> None:
    scenario = build_simulated_care_scenario()
    by_key = {moment.moment: moment for moment in scenario.moments}

    bathroom = by_key["bathroom_timeout"]
    assert bathroom.facts.zone_label == "卫生间"
    assert bathroom.facts.observed_duration_min == 31
    assert bathroom.facts.threshold_min == 20
    assert bathroom.facts.threshold_comparison == "exceeded"
    assert "simulated_external_zone_presence" in bathroom.facts.input_sources
    assert bathroom.facts.unknowns

    pet = by_key["pet_night"]
    assert pet.event_type == "pet_activity_external_label"
    assert "simulated_external_multisensor_label" in pet.facts.input_sources
    assert "Wi-Fi CSI 本身不能识别宠物" in pet.conclusion

    fall = by_key["fall_drill"]
    assert fall.event_type == "suspected_fall_drill"
    assert fall.scenario_only is True
    assert "simulated_manual_fall_drill_label" in fall.facts.input_sources
    assert "不是当前硬件的真实检测结果" in fall.conclusion
    assert "模拟 Wi-Fi 代理的单一演练快照显示活动突变" in fall.facts.plain_facts
    assert all("快速变化后低活动" not in fact for fact in fall.facts.plain_facts)
    assert all("快速变化后低活动" not in fact for fact in fall.what_agent_knows)


def test_pet_classification_without_external_simulated_label_is_rejected() -> None:
    payload = build_simulated_care_scenario("pet_night").model_dump(mode="json")
    pet = payload["moments"][3]
    pet["evidence_core"]["external_observations"] = [
        observation
        for observation in pet["evidence_core"]["external_observations"]
        if observation["source"] != "simulated_external_multisensor_label"
    ]
    _rehash_moment(payload, 3)

    with pytest.raises(ValidationError, match="required fresh observations"):
        SimulatedCareScenario.model_validate(payload)


def test_fall_scenario_without_manual_drill_label_is_rejected() -> None:
    payload = build_simulated_care_scenario("fall_drill").model_dump(mode="json")
    fall = payload["moments"][2]
    fall["evidence_core"]["external_observations"] = [
        observation
        for observation in fall["evidence_core"]["external_observations"]
        if observation["source"] != "simulated_manual_fall_drill_label"
    ]
    _rehash_moment(payload, 2)

    with pytest.raises(ValidationError, match="required fresh observations"):
        SimulatedCareScenario.model_validate(payload)


def test_bathroom_duration_without_external_zone_presence_is_rejected() -> None:
    payload = build_simulated_care_scenario("bathroom_timeout").model_dump(
        mode="json"
    )
    bathroom = payload["moments"][1]
    bathroom["evidence_core"]["external_observations"] = [
        observation
        for observation in bathroom["evidence_core"]["external_observations"]
        if observation["source"] != "simulated_external_zone_presence"
    ]
    _rehash_moment(payload, 1)

    with pytest.raises(ValidationError, match="required fresh observations"):
        SimulatedCareScenario.model_validate(payload)


def test_missing_wifi_observation_is_rejected() -> None:
    payload = build_simulated_care_scenario("bathroom_timeout").model_dump(
        mode="json"
    )
    bathroom = payload["moments"][1]
    bathroom["evidence_core"]["external_observations"] = [
        observation
        for observation in bathroom["evidence_core"]["external_observations"]
        if observation["source"] != "simulated_wifi_proxy"
    ]
    _rehash_moment(payload, 1)

    with pytest.raises(ValidationError, match="simulated_wifi_proxy"):
        SimulatedCareScenario.model_validate(payload)


def test_expired_external_observation_is_rejected() -> None:
    payload = build_simulated_care_scenario("bathroom_timeout").model_dump(
        mode="json"
    )
    bathroom = payload["moments"][1]
    bathroom["evidence_core"]["external_observations"][1]["valid_until"] = (
        "2026-08-13T12:44:50+08:00"
    )
    _rehash_moment(payload, 1)

    with pytest.raises(ValidationError, match="fresh"):
        SimulatedCareScenario.model_validate(payload)


def test_cross_zone_external_observation_is_rejected() -> None:
    payload = build_simulated_care_scenario("bathroom_timeout").model_dump(
        mode="json"
    )
    payload["moments"][1]["evidence_core"]["external_observations"][1][
        "zone_id"
    ] = "bedroom"
    _rehash_moment(payload, 1)

    with pytest.raises(ValidationError, match="same event and zone"):
        SimulatedCareScenario.model_validate(payload)


def test_cross_event_external_observation_is_rejected() -> None:
    payload = build_simulated_care_scenario("pet_night").model_dump(mode="json")
    payload["moments"][3]["evidence_core"]["external_observations"][2][
        "event_id"
    ] = "care-event-routine"
    _rehash_moment(payload, 3)

    with pytest.raises(ValidationError, match="same event and zone"):
        SimulatedCareScenario.model_validate(payload)


def test_conflicting_external_subject_labels_are_rejected() -> None:
    payload = build_simulated_care_scenario("pet_night").model_dump(mode="json")
    observations = payload["moments"][3]["evidence_core"][
        "external_observations"
    ]
    conflicting = dict(observations[2])
    conflicting["observation_id"] = "conflicting-person-label"
    conflicting["value"] = "person"
    observations.append(conflicting)

    with pytest.raises(ValidationError, match="conflicting or duplicate"):
        SimulatedCareScenario.model_validate(payload)


def test_external_observation_from_another_session_is_rejected() -> None:
    payload = build_simulated_care_scenario("fall_drill").model_dump(mode="json")
    payload["moments"][2]["evidence_core"]["external_observations"][2][
        "session_id"
    ] = "another-simulated-session"
    _rehash_moment(payload, 2)

    with pytest.raises(ValidationError, match="session does not match"):
        SimulatedCareScenario.model_validate(payload)


def test_evidence_core_change_rejects_old_hash() -> None:
    payload = build_simulated_care_scenario("bathroom_timeout").model_dump(
        mode="json"
    )
    payload["moments"][1]["evidence_core"]["threshold_min"] = 21

    with pytest.raises(ValidationError, match="canonical evidence core"):
        SimulatedCareScenario.model_validate(payload)


def _degrade_required_observation(payload: dict, index: int, source: str) -> None:
    observations = payload["moments"][index]["evidence_core"][
        "external_observations"
    ]
    observation = next(item for item in observations if item["source"] == source)
    observation["quality_status"] = "degraded"


def _withhold_degraded_projection(payload: dict, index: int) -> None:
    moment = payload["moments"][index]
    moment["interpretation_status"] = "unknown"
    moment["conclusion_confidence"] = 0.25
    for suggestion in moment["suggestions"]:
        suggestion["execution_status"] = "withheld"
        suggestion["target"] = "none"
        suggestion["reason_code"] = "degraded_evidence"
        suggestion["action_confidence"] = 0.25


@pytest.mark.parametrize(
    "moment,index,source",
    [
        ("bathroom_timeout", 1, "simulated_wifi_proxy"),
        ("bathroom_timeout", 1, "simulated_external_zone_presence"),
        ("fall_drill", 2, "simulated_manual_fall_drill_label"),
        ("pet_night", 3, "simulated_external_multisensor_label"),
    ],
)
def test_any_degraded_required_observation_rejects_active_suggestions(
    moment: CareMomentKey,
    index: int,
    source: str,
) -> None:
    payload = build_simulated_care_scenario(moment).model_dump(mode="json")
    _degrade_required_observation(payload, index, source)
    payload["moments"][index]["conclusion_confidence"] = 0.25
    for suggestion in payload["moments"][index]["suggestions"]:
        suggestion["action_confidence"] = 0.25
    _rehash_moment(payload, index)

    with pytest.raises(ValidationError, match="unknown interpretation status"):
        SimulatedCareScenario.model_validate(payload)


def test_degraded_required_observation_rejects_high_conclusion_confidence() -> None:
    payload = build_simulated_care_scenario("bathroom_timeout").model_dump(
        mode="json"
    )
    _degrade_required_observation(payload, 1, "simulated_external_zone_presence")
    _withhold_degraded_projection(payload, 1)
    payload["moments"][1]["conclusion_confidence"] = 0.26
    _rehash_moment(payload, 1)

    with pytest.raises(ValidationError, match="caps conclusion confidence"):
        SimulatedCareScenario.model_validate(payload)


def test_degraded_required_observation_accepts_fail_closed_projection() -> None:
    payload = build_simulated_care_scenario("bathroom_timeout").model_dump(
        mode="json"
    )
    _degrade_required_observation(payload, 1, "simulated_external_zone_presence")
    _withhold_degraded_projection(payload, 1)
    _rehash_moment(payload, 1)

    scenario = SimulatedCareScenario.model_validate(payload)
    moment = scenario.moments[1]
    assert moment.interpretation_status == "unknown"
    assert moment.conclusion_confidence == 0.25
    assert all(
        suggestion.execution_status == "withheld"
        and suggestion.target == "none"
        and suggestion.reason_code == "degraded_evidence"
        for suggestion in moment.suggestions
    )


def test_degraded_proxy_triplet_rejects_active_suggestions_after_rehash() -> None:
    payload = build_simulated_care_scenario("bathroom_timeout").model_dump(
        mode="json"
    )
    payload["moments"][1]["evidence_core"]["proxy_triplet"]["status"] = (
        "degraded"
    )
    payload["moments"][1]["interpretation_status"] = "unknown"
    payload["moments"][1]["conclusion_confidence"] = 0.25
    for suggestion in payload["moments"][1]["suggestions"]:
        suggestion["action_confidence"] = 0.25
    _rehash_moment(payload, 1)

    with pytest.raises(ValidationError, match="withhold every suggestion"):
        SimulatedCareScenario.model_validate(payload)


def test_supported_interpretation_is_impossible_with_degraded_proxy() -> None:
    payload = build_simulated_care_scenario("bathroom_timeout").model_dump(
        mode="json"
    )
    payload["moments"][1]["evidence_core"]["proxy_triplet"]["status"] = (
        "degraded"
    )
    _rehash_moment(payload, 1)

    with pytest.raises(ValidationError, match="unknown interpretation status"):
        SimulatedCareScenario.model_validate(payload)


def test_conservative_unknown_with_all_ok_evidence_is_allowed_fail_closed() -> None:
    payload = build_simulated_care_scenario("bathroom_timeout").model_dump(
        mode="json"
    )
    _withhold_degraded_projection(payload, 1)

    scenario = SimulatedCareScenario.model_validate(payload)
    moment = scenario.moments[1]
    assert moment.interpretation_status == "unknown"
    assert moment.conclusion_confidence == 0.25
    assert all(
        suggestion.execution_status == "withheld"
        and suggestion.target == "none"
        and suggestion.reason_code == "degraded_evidence"
        for suggestion in moment.suggestions
    )


def test_care_conclusion_confidence_cannot_exceed_sensor_cap() -> None:
    payload = build_simulated_care_scenario().model_dump()
    payload["moments"][1]["conclusion_confidence"] = 0.99

    with pytest.raises(ValidationError, match="sensor_confidence_cap"):
        SimulatedCareScenario.model_validate(payload)


def test_simulated_day_is_chronological_and_within_declared_bounds() -> None:
    scenario = build_simulated_care_scenario()

    assert (scenario.day_ended_at - scenario.day_started_at).total_seconds() == 86400
    assert all(
        scenario.day_started_at <= entry.started_at < entry.ended_at <= scenario.day_ended_at
        for entry in scenario.timeline
    )
    assert all(
        previous.started_at <= current.started_at
        for previous, current in zip(scenario.timeline, scenario.timeline[1:], strict=False)
    )


def test_unsorted_timeline_is_rejected() -> None:
    payload = build_simulated_care_scenario().model_dump(mode="json")
    payload["timeline"][0], payload["timeline"][1] = (
        payload["timeline"][1],
        payload["timeline"][0],
    )

    with pytest.raises(ValidationError, match="sorted by started_at"):
        SimulatedCareScenario.model_validate(payload)


def test_overlapping_timeline_entries_are_rejected() -> None:
    payload = build_simulated_care_scenario().model_dump(mode="json")
    payload["timeline"][1]["started_at"] = "2026-08-13T06:42:00+08:00"

    with pytest.raises(ValidationError, match="must not overlap"):
        SimulatedCareScenario.model_validate(payload)
