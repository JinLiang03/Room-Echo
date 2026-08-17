"""Explicitly simulated ageing-in-place scenario contracts.

These records are presentation fixtures, not measured care outcomes.  They
make the scenario inputs and action boundaries machine-checkable so a UI can
demonstrate a care workflow without claiming that current Wi-Fi CSI hardware
recognises a person, a pet, a room, or a fall.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .base import HASH_PATTERN, SCHEMA_BASE
from .signals import SignalTriplet

CareMomentKey = Literal[
    "routine",
    "bathroom_timeout",
    "fall_drill",
    "pet_night",
]
CareInputSource = Literal[
    "simulated_wifi_proxy",
    "simulated_external_zone_presence",
    "simulated_external_multisensor_label",
    "simulated_manual_fall_drill_label",
    "simulated_care_rule",
    "simulated_clock",
]
CareSuggestionKind = Literal[
    "ambient_light_preview",
    "voice_checkin_preview",
    "family_notification_draft",
    "robot_inspection_preview",
]
CareSuggestionTarget = Literal[
    "ui_light_preview",
    "speaker_script_preview",
    "family_message_draft",
    "robot_task_preview",
    "none",
]
CareSuggestionReasonCode = Literal[
    "scenario_preview_only",
    "not_needed",
    "human_confirmation_required",
    "external_adapter_unavailable",
    "external_label_resolved",
    "degraded_evidence",
]
CareObservationSource = Literal[
    "simulated_wifi_proxy",
    "simulated_external_zone_presence",
    "simulated_external_multisensor_label",
    "simulated_manual_fall_drill_label",
]
CareObservationValue = Literal[
    "activity_change",
    "quiet",
    "zone_present",
    "zone_absent",
    "pet",
    "person",
    "unknown_subject",
    "fall_drill",
    "cancelled_drill",
]
CareEventType = Literal[
    "routine_check",
    "bathroom_duration_exceeded",
    "suspected_fall_drill",
    "pet_activity_external_label",
]


class SimulatedResidentProfile(BaseModel):
    """Anonymous fictional resident data used only by the demo scenario."""

    model_config = ConfigDict(extra="forbid")

    profile_id: str = Field(min_length=1)
    display_name: str = Field(min_length=1, max_length=40)
    profile_origin: Literal["fictional_simulation"]
    age_band: Literal["75-79"]
    living_arrangement: Literal["lives_alone_simulation"]
    mobility_context: list[str] = Field(min_length=1)
    household_context: list[str] = Field(min_length=1)
    care_preferences: list[str] = Field(min_length=1)
    contains_real_person_data: Literal[False]


class SimulatedHomeZone(BaseModel):
    """One fictional floor-plan zone; never inferred from CSI."""

    model_config = ConfigDict(extra="forbid")

    zone_id: str = Field(min_length=1)
    label: str = Field(min_length=1, max_length=32)
    approximate_area_m2: float = Field(gt=0)
    adjacent_zone_ids: list[str] = Field(default_factory=list)
    simulated_inputs: list[CareInputSource] = Field(min_length=1)


class SimulatedHomeLayout(BaseModel):
    """Fictional home metadata supplied by the scenario, not sensed layout."""

    model_config = ConfigDict(extra="forbid")

    home_id: str = Field(min_length=1)
    label: str = Field(min_length=1, max_length=60)
    layout_source: Literal["simulated_fixture_not_sensor_inferred"]
    approximate_area_m2: float = Field(gt=0)
    zones: list[SimulatedHomeZone] = Field(min_length=1)
    notes: list[str] = Field(min_length=1)

    @model_validator(mode="after")
    def _zone_links_are_valid(self) -> SimulatedHomeLayout:
        zone_ids = [zone.zone_id for zone in self.zones]
        if len(zone_ids) != len(set(zone_ids)):
            raise ValueError("home zone ids must be unique")
        known = set(zone_ids)
        for zone in self.zones:
            if any(adjacent not in known for adjacent in zone.adjacent_zone_ids):
                raise ValueError("adjacent zone id is not present in the layout")
        return self


class SimulatedActivityEntry(BaseModel):
    """One scripted entry in a 24-hour fictional activity timeline."""

    model_config = ConfigDict(extra="forbid")

    entry_id: str = Field(min_length=1)
    started_at: datetime
    ended_at: datetime
    zone_id: str = Field(min_length=1)
    activity_label: str = Field(min_length=1, max_length=80)
    status: Literal["routine", "attention", "warning", "drill", "external_label"]
    input_sources: list[CareInputSource] = Field(min_length=1)
    event_id: str | None = None
    note: str = Field(min_length=1, max_length=240)

    @model_validator(mode="after")
    def _timeline_interval_is_positive(self) -> SimulatedActivityEntry:
        if self.ended_at <= self.started_at:
            raise ValueError("activity entry ended_at must be after started_at")
        return self


class CareMomentFacts(BaseModel):
    """Plain-language, inspectable inputs behind one simulated conclusion."""

    model_config = ConfigDict(extra="forbid")

    zone_id: str = Field(min_length=1)
    zone_label: str = Field(min_length=1, max_length=32)
    observed_duration_min: float = Field(ge=0)
    threshold_min: float = Field(gt=0)
    threshold_comparison: Literal["within", "exceeded"]
    input_sources: list[CareInputSource] = Field(min_length=1)
    plain_facts: list[str] = Field(min_length=4, max_length=8)
    unknowns: list[str] = Field(min_length=1)
    evidence_refs: list[str] = Field(min_length=1)

    @model_validator(mode="after")
    def _comparison_matches_values(self) -> CareMomentFacts:
        expected = (
            "exceeded"
            if self.observed_duration_min > self.threshold_min
            else "within"
        )
        if self.threshold_comparison != expected:
            raise ValueError("threshold comparison does not match duration values")
        return self


class SimulatedExternalObservation(BaseModel):
    """One expiring, event-bound input supplied by the fictional scenario.

    These observations are not raw CSI and not real integrations.  The source,
    event, session, zone, validity interval and quality are explicit so stale
    or cross-zone labels cannot silently support a care conclusion.
    """

    model_config = ConfigDict(extra="forbid")

    observation_id: str = Field(min_length=1)
    simulation_only: Literal[True]
    source: CareObservationSource
    observed_at: datetime
    valid_until: datetime
    zone_id: str = Field(min_length=1)
    quality_status: Literal["ok", "degraded"]
    session_id: str = Field(min_length=1)
    event_id: str = Field(min_length=1)
    value: CareObservationValue

    @model_validator(mode="after")
    def _observation_is_well_formed(self) -> SimulatedExternalObservation:
        if self.valid_until <= self.observed_at:
            raise ValueError("external observation valid_until must follow observed_at")
        allowed_values: dict[CareObservationSource, set[CareObservationValue]] = {
            "simulated_wifi_proxy": {"activity_change", "quiet"},
            "simulated_external_zone_presence": {"zone_present", "zone_absent"},
            "simulated_external_multisensor_label": {
                "pet",
                "person",
                "unknown_subject",
            },
            "simulated_manual_fall_drill_label": {
                "fall_drill",
                "cancelled_drill",
            },
        }
        if self.value not in allowed_values[self.source]:
            raise ValueError("external observation value does not match its source")
        return self


class CareMomentEvidenceCore(BaseModel):
    """Canonical evidence-only content hashed for one simulated care moment."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["care-evidence-core.v2"]
    event_id: str = Field(min_length=1)
    timeline_entry_id: str = Field(min_length=1)
    event_type: CareEventType
    occurred_at: datetime
    zone_id: str = Field(min_length=1)
    observed_duration_min: float = Field(ge=0)
    threshold_min: float = Field(gt=0)
    threshold_comparison: Literal["within", "exceeded"]
    input_sources: list[CareInputSource] = Field(min_length=1)
    external_observations: list[SimulatedExternalObservation] = Field(min_length=1)
    proxy_triplet: SignalTriplet
    sensor_confidence_cap: float = Field(ge=0, le=1)

    @model_validator(mode="after")
    def _core_is_self_consistent(self) -> CareMomentEvidenceCore:
        expected_comparison = (
            "exceeded"
            if self.observed_duration_min > self.threshold_min
            else "within"
        )
        if self.threshold_comparison != expected_comparison:
            raise ValueError("evidence-core threshold comparison is inconsistent")
        if len(self.input_sources) != len(set(self.input_sources)):
            raise ValueError("evidence-core input sources must be unique")
        observation_sources = [
            observation.source for observation in self.external_observations
        ]
        if len(observation_sources) != len(set(observation_sources)):
            raise ValueError("conflicting or duplicate external observations")
        if any(source not in self.input_sources for source in observation_sources):
            raise ValueError("external observation source is absent from input_sources")
        if self.proxy_triplet.source_mode != "mock":
            raise ValueError("care proxy triplet source_mode must be mock")
        if self.proxy_triplet.window_id != f"{self.event_id}-proxy-final":
            raise ValueError("care proxy triplet window must bind to the same care event")
        if self.proxy_triplet.ended_at != self.occurred_at:
            raise ValueError("care proxy triplet must end at the care moment occurred_at")
        if self.proxy_triplet.sensor_confidence_cap != self.sensor_confidence_cap:
            raise ValueError(
                "care proxy triplet sensor cap must match the evidence-core cap"
            )
        if self.proxy_triplet.status not in {"ok", "degraded"}:
            raise ValueError("care proxy triplet must be usable or explicitly degraded")
        return self


def canonical_care_evidence_hash(core: CareMomentEvidenceCore) -> str:
    """Hash normalized evidence content, excluding prose and self-references."""
    canonical = json.dumps(
        core.model_dump(mode="json"),
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(canonical).hexdigest()


def _allowed_care_evidence_paths(core: CareMomentEvidenceCore) -> set[str]:
    """Return resolvable canonical paths contained in the hashed evidence core."""
    paths = {
        "evidence_core/schema_version",
        "evidence_core/event_id",
        "evidence_core/timeline_entry_id",
        "evidence_core/event_type",
        "evidence_core/occurred_at",
        "evidence_core/zone_id",
        "evidence_core/observed_duration_min",
        "evidence_core/threshold_min",
        "evidence_core/threshold_comparison",
        "evidence_core/input_sources",
        "evidence_core/sensor_confidence_cap",
        "evidence_core/proxy_triplet/schema_version",
        "evidence_core/proxy_triplet/session_id",
        "evidence_core/proxy_triplet/window_id",
        "evidence_core/proxy_triplet/source_mode",
        "evidence_core/proxy_triplet/started_at",
        "evidence_core/proxy_triplet/ended_at",
        "evidence_core/proxy_triplet/motion/value",
        "evidence_core/proxy_triplet/motion/state",
        "evidence_core/proxy_triplet/motion/confidence",
        "evidence_core/proxy_triplet/occupancy_density/probabilities/low",
        "evidence_core/proxy_triplet/occupancy_density/probabilities/medium",
        "evidence_core/proxy_triplet/occupancy_density/probabilities/high",
        "evidence_core/proxy_triplet/occupancy_density/probabilities/unknown",
        "evidence_core/proxy_triplet/occupancy_density/state",
        "evidence_core/proxy_triplet/occupancy_density/confidence",
        "evidence_core/proxy_triplet/depth_zone/probabilities/near",
        "evidence_core/proxy_triplet/depth_zone/probabilities/mid",
        "evidence_core/proxy_triplet/depth_zone/probabilities/far",
        "evidence_core/proxy_triplet/depth_zone/probabilities/unknown",
        "evidence_core/proxy_triplet/depth_zone/state",
        "evidence_core/proxy_triplet/depth_zone/confidence",
        "evidence_core/proxy_triplet/sensor_confidence_cap",
        "evidence_core/proxy_triplet/evidence_refs",
        "evidence_core/proxy_triplet/status",
    }
    observation_fields = {
        "observation_id",
        "simulation_only",
        "source",
        "observed_at",
        "valid_until",
        "zone_id",
        "quality_status",
        "session_id",
        "event_id",
        "value",
    }
    for observation in core.external_observations:
        base = f"evidence_core/external_observations/{observation.observation_id}"
        paths.update(f"{base}/{field}" for field in observation_fields)
    return paths


class SimulatedCareSuggestion(BaseModel):
    """A UI-only preview or withheld intent; never a device command receipt."""

    model_config = ConfigDict(extra="forbid")

    suggestion_id: str = Field(min_length=1)
    kind: CareSuggestionKind
    title: str = Field(min_length=1, max_length=40)
    detail: str = Field(min_length=1, max_length=240)
    preview_copy: str = Field(min_length=1, max_length=240)
    execution_status: Literal["simulated_preview", "withheld"]
    target: CareSuggestionTarget
    reason_code: CareSuggestionReasonCode
    requires_human_confirmation: bool
    external_execution_allowed: Literal[False]
    evidence_refs: list[str] = Field(min_length=1)
    action_confidence: float = Field(ge=0, le=1)
    sensor_confidence_cap: float = Field(ge=0, le=1)

    @model_validator(mode="after")
    def _enforce_preview_boundary(self) -> SimulatedCareSuggestion:
        if self.action_confidence > self.sensor_confidence_cap:
            raise ValueError(
                "action_confidence <= sensor_confidence_cap invariant violated"
            )
        preview_targets: dict[CareSuggestionKind, CareSuggestionTarget] = {
            "ambient_light_preview": "ui_light_preview",
            "voice_checkin_preview": "speaker_script_preview",
            "family_notification_draft": "family_message_draft",
            "robot_inspection_preview": "robot_task_preview",
        }
        if self.execution_status == "simulated_preview":
            if self.target != preview_targets[self.kind]:
                raise ValueError("simulated suggestion target does not match its kind")
        elif self.target != "none":
            raise ValueError("withheld suggestion must not have an execution target")
        if self.kind in {
            "voice_checkin_preview",
            "family_notification_draft",
            "robot_inspection_preview",
        } and not self.requires_human_confirmation:
            raise ValueError("external-facing suggestion requires human confirmation")
        return self


class SimulatedCareMoment(BaseModel):
    """One deterministic scenario event and the Agent's bounded response."""

    model_config = ConfigDict(extra="forbid")

    moment: CareMomentKey
    event_id: str = Field(min_length=1)
    timeline_entry_id: str = Field(min_length=1)
    event_type: CareEventType
    severity: Literal["normal", "attention", "warning", "urgent_drill"]
    occurred_at: datetime
    scenario_only: Literal[True]
    evidence_core: CareMomentEvidenceCore
    evidence_hash: str = Field(pattern=HASH_PATTERN)
    facts: CareMomentFacts
    headline: str = Field(min_length=1, max_length=80)
    conclusion: str = Field(min_length=1, max_length=360)
    what_agent_knows: list[str] = Field(min_length=1)
    what_agent_does_not_know: list[str] = Field(min_length=1)
    interpretation_status: Literal["supported", "unknown"]
    conclusion_confidence: float = Field(ge=0, le=1)
    sensor_confidence_cap: float = Field(ge=0, le=1)
    suggestions: list[SimulatedCareSuggestion] = Field(min_length=4, max_length=4)

    @model_validator(mode="after")
    def _enforce_scenario_evidence_and_actions(self) -> SimulatedCareMoment:
        expected_event_type = {
            "routine": "routine_check",
            "bathroom_timeout": "bathroom_duration_exceeded",
            "fall_drill": "suspected_fall_drill",
            "pet_night": "pet_activity_external_label",
        }[self.moment]
        if self.event_type != expected_event_type:
            raise ValueError("care event type does not match selected moment")
        if self.evidence_core.event_id != self.event_id:
            raise ValueError("evidence core event_id does not match care moment")
        if self.evidence_core.timeline_entry_id != self.timeline_entry_id:
            raise ValueError("evidence core timeline entry does not match care moment")
        if self.evidence_core.event_type != self.event_type:
            raise ValueError("evidence core event type does not match care moment")
        if self.evidence_core.occurred_at != self.occurred_at:
            raise ValueError("evidence core occurred_at does not match care moment")
        if self.evidence_hash != canonical_care_evidence_hash(self.evidence_core):
            raise ValueError("evidence_hash does not match canonical evidence core")
        if (
            self.facts.zone_id != self.evidence_core.zone_id
            or self.facts.observed_duration_min
            != self.evidence_core.observed_duration_min
            or self.facts.threshold_min != self.evidence_core.threshold_min
            or self.facts.threshold_comparison
            != self.evidence_core.threshold_comparison
            or self.facts.input_sources != self.evidence_core.input_sources
            or self.sensor_confidence_cap
            != self.evidence_core.sensor_confidence_cap
        ):
            raise ValueError("plain facts do not match the canonical evidence core")
        if self.conclusion_confidence > self.sensor_confidence_cap:
            raise ValueError(
                "conclusion_confidence <= sensor_confidence_cap invariant violated"
            )
        prefix = f"evidence://{self.evidence_hash}/"
        refs = [*self.facts.evidence_refs]
        refs.extend(
            ref for suggestion in self.suggestions for ref in suggestion.evidence_refs
        )
        if any(not ref.startswith(prefix) for ref in refs):
            raise ValueError("care evidence refs must bind to the moment evidence_hash")
        allowed_paths = _allowed_care_evidence_paths(self.evidence_core)
        unresolved_paths = [
            ref.removeprefix(prefix) for ref in refs if ref.removeprefix(prefix) not in allowed_paths
        ]
        if unresolved_paths:
            raise ValueError(
                "care evidence ref does not resolve to the hashed evidence core: "
                + ", ".join(sorted(set(unresolved_paths)))
            )
        expected_kinds: set[CareSuggestionKind] = {
            "ambient_light_preview",
            "voice_checkin_preview",
            "family_notification_draft",
            "robot_inspection_preview",
        }
        if {suggestion.kind for suggestion in self.suggestions} != expected_kinds:
            raise ValueError("each care moment requires four distinct suggestion kinds")
        if any(
            suggestion.sensor_confidence_cap != self.sensor_confidence_cap
            or suggestion.action_confidence > self.conclusion_confidence
            for suggestion in self.suggestions
        ):
            raise ValueError(
                "suggestion confidence must be bound to the moment confidence chain"
            )
        observations = {
            observation.source: observation
            for observation in self.evidence_core.external_observations
        }
        required_sources: set[CareObservationSource] = {
            "simulated_wifi_proxy",
            "simulated_external_zone_presence",
        }
        if self.moment == "pet_night":
            required_sources.add("simulated_external_multisensor_label")
        if self.moment == "fall_drill":
            required_sources.add("simulated_manual_fall_drill_label")
        missing = required_sources - observations.keys()
        if missing:
            raise ValueError(
                "care moment is missing required fresh observations: "
                + ", ".join(sorted(missing))
            )
        if any(
            observation.event_id != self.event_id
            or observation.zone_id != self.facts.zone_id
            or not (
                observation.observed_at
                <= self.occurred_at
                <= observation.valid_until
            )
            for observation in observations.values()
        ):
            raise ValueError(
                "external observation must be fresh and bound to the same event and zone"
            )
        if observations["simulated_external_zone_presence"].value != "zone_present":
            raise ValueError("care moment requires a non-conflicting zone-present label")
        if self.moment == "pet_night" and (
            observations["simulated_external_multisensor_label"].value != "pet"
        ):
            raise ValueError("pet moment has a conflicting external subject label")
        if self.moment == "fall_drill" and (
            observations["simulated_manual_fall_drill_label"].value != "fall_drill"
        ):
            raise ValueError("fall moment has a conflicting manual drill label")
        required_observations = [observations[source] for source in required_sources]
        evidence_degraded = self.evidence_core.proxy_triplet.status == "degraded" or any(
            observation.quality_status == "degraded"
            for observation in required_observations
        )
        if evidence_degraded and self.interpretation_status != "unknown":
            raise ValueError(
                "degraded required evidence requires unknown interpretation status"
            )
        if self.interpretation_status == "unknown":
            if self.conclusion_confidence > min(0.25, self.sensor_confidence_cap):
                raise ValueError(
                    "unknown care interpretation caps conclusion confidence at 0.25"
                )
            if any(
                suggestion.execution_status != "withheld"
                or suggestion.target != "none"
                or suggestion.reason_code != "degraded_evidence"
                for suggestion in self.suggestions
            ):
                raise ValueError(
                    "unknown care interpretation must withhold every suggestion"
                )
        return self


class SimulatedCareScenario(BaseModel):
    """Full deterministic 24-hour care demo with one selected UI moment."""

    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "$id": f"{SCHEMA_BASE}/simulated_care_scenario.schema.json",
            "title": "SimulatedCareScenario",
        },
    )

    schema_version: Literal["simulated-care-scenario.v2"]
    scenario_id: str = Field(min_length=1)
    simulation_only: Literal[True]
    source_mode: Literal["mock"]
    device_execution_enabled: Literal[False]
    resident: SimulatedResidentProfile
    home: SimulatedHomeLayout
    day_started_at: datetime
    day_ended_at: datetime
    timeline: list[SimulatedActivityEntry] = Field(min_length=1)
    moments: list[SimulatedCareMoment] = Field(min_length=4, max_length=4)
    selected_moment: CareMomentKey
    current_index: int = Field(ge=0, le=3)
    truth_boundary: list[str] = Field(min_length=1)
    generated_at: datetime

    @model_validator(mode="after")
    def _scenario_is_coherent(self) -> SimulatedCareScenario:
        if self.day_ended_at <= self.day_started_at:
            raise ValueError("scenario day end must follow its start")
        zone_ids = {zone.zone_id for zone in self.home.zones}
        timeline_ids = {entry.entry_id for entry in self.timeline}
        if len(timeline_ids) != len(self.timeline):
            raise ValueError("timeline entry ids must be unique")
        if any(entry.zone_id not in zone_ids for entry in self.timeline):
            raise ValueError("timeline entry references an unknown home zone")
        if any(
            entry.started_at < self.day_started_at
            or entry.ended_at > self.day_ended_at
            for entry in self.timeline
        ):
            raise ValueError("timeline entry falls outside the simulated day")
        for previous, current in zip(
            self.timeline,
            self.timeline[1:],
            strict=False,
        ):
            if current.started_at < previous.started_at:
                raise ValueError("timeline entries must be sorted by started_at")
            if current.started_at < previous.ended_at:
                raise ValueError("timeline entries must not overlap")
        expected_moments: set[CareMomentKey] = {
            "routine",
            "bathroom_timeout",
            "fall_drill",
            "pet_night",
        }
        if {moment.moment for moment in self.moments} != expected_moments:
            raise ValueError("scenario must expose all four deterministic moments")
        if any(moment.facts.zone_id not in zone_ids for moment in self.moments):
            raise ValueError("care moment references an unknown home zone")
        if any(
            moment.timeline_entry_id not in timeline_ids for moment in self.moments
        ):
            raise ValueError("care moment references an unknown timeline entry")
        entries_by_id = {entry.entry_id: entry for entry in self.timeline}
        zone_labels = {zone.zone_id: zone.label for zone in self.home.zones}
        proxy_window_ids = [
            moment.evidence_core.proxy_triplet.window_id for moment in self.moments
        ]
        if len(proxy_window_ids) != len(set(proxy_window_ids)):
            raise ValueError("care proxy triplet window ids must be unique")
        for moment in self.moments:
            entry = entries_by_id[moment.timeline_entry_id]
            proxy_triplet = moment.evidence_core.proxy_triplet
            if entry.event_id != moment.event_id:
                raise ValueError("care moment event_id does not match timeline entry")
            if entry.zone_id != moment.facts.zone_id:
                raise ValueError("care moment zone does not match timeline entry")
            if zone_labels[entry.zone_id] != moment.facts.zone_label:
                raise ValueError("care moment zone label does not match home layout")
            if entry.ended_at != moment.occurred_at:
                raise ValueError("care moment occurred_at must equal timeline entry end")
            if entry.input_sources != moment.facts.input_sources:
                raise ValueError("care moment sources do not match timeline entry")
            duration_min = (entry.ended_at - entry.started_at).total_seconds() / 60
            if duration_min != moment.facts.observed_duration_min:
                raise ValueError("care moment duration does not match timeline entry")
            if proxy_triplet.session_id != self.scenario_id:
                raise ValueError("care proxy triplet session does not match scenario")
            if proxy_triplet.source_mode != self.source_mode:
                raise ValueError("care proxy triplet source does not match scenario")
            if not (
                entry.started_at
                <= proxy_triplet.started_at
                <= proxy_triplet.ended_at
                <= entry.ended_at
            ):
                raise ValueError(
                    "care proxy triplet time must fall within its timeline entry"
                )
            expected_ref = (
                f"fixture://{self.scenario_id}/proxy/{proxy_triplet.window_id}"
            )
            if proxy_triplet.evidence_refs != [expected_ref]:
                raise ValueError(
                    "care proxy triplet evidence ref must identify its simulated fixture"
                )
            for observation in moment.evidence_core.external_observations:
                if observation.session_id != self.scenario_id:
                    raise ValueError(
                        "external observation session does not match scenario"
                    )
                if not entry.started_at <= observation.observed_at <= entry.ended_at:
                    raise ValueError(
                        "external observation time does not match timeline entry"
                    )
        if self.moments[self.current_index].moment != self.selected_moment:
            raise ValueError("current_index does not point to selected_moment")
        return self
