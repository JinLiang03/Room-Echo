"""Auditable agent claims, challenges, and the final council result."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .actions import AgentActionDecision
from .base import HASH_PATTERN, SCHEMA_BASE

AgentRole = Literal[
    "architecture",
    "biota",
    "feng_shui",
    "psyche",
    "soundscape",
    "skeptic",
    "fusion",
]


class AnalysisStep(BaseModel):
    """One visible reasoning step in an agent's analysis trace."""

    model_config = ConfigDict(extra="forbid")

    step_id: str = Field(min_length=1)
    phase: Literal[
        "observe",
        "compare",
        "retrieve",
        "map",
        "reason",
        "challenge",
        "conclude",
    ]
    title: str = Field(min_length=1)
    text: str = Field(min_length=1)
    evidence_refs: list[str] = Field(default_factory=list)


class ReadingLayer(BaseModel):
    """One signal's systematic reading within a persona interpretation."""

    model_config = ConfigDict(extra="forbid")

    signal: Literal["motion", "occupancy", "depth"]
    state: str = Field(min_length=1)
    metaphor: str = Field(min_length=1)
    explanation: str = Field(min_length=1)


class SystematicReading(BaseModel):
    """A structured, persona-voiced interpretation of the full evidence packet.

    Everything here is interpretation of calibrated proxy signals; no field
    may quote a numeric measurement or claim sensor-equivalent perception.
    """

    model_config = ConfigDict(extra="forbid")

    headline: str = Field(min_length=1)
    scene_sketch: str = Field(min_length=1)
    layers: list[ReadingLayer] = Field(min_length=1)
    narrative: str = Field(min_length=1)
    boundary_notes: list[str] = Field(default_factory=list)
    multimodal_hints: list[str] = Field(default_factory=list)


class AgentContinuity(BaseModel):
    """Deterministic link from one role's current reading to its prior cycle.

    The Council runtime computes this record from sealed proxy states and
    committed role outputs. Providers cannot write it, and it never feeds the
    sensing values or confidence chain.
    """

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["agent-continuity.v1"] = "agent-continuity.v1"
    previous_cycle_id: str | None = None
    previous_record_id: str | None = None
    previous_evidence_hash: str | None = Field(default=None, pattern=HASH_PATTERN)
    relation: Literal[
        "initial",
        "steady",
        "intensified",
        "eased",
        "shifted",
        "quality_changed",
        "recovered",
        "unknown",
    ]
    changed_signals: list[Literal["motion", "occupancy", "depth", "quality"]] = Field(
        default_factory=list
    )
    summary: str = Field(min_length=1, max_length=240)


SpecialistPresentationState = Literal[
    "tightening",
    "expanding",
    "blocked",
    "resting",
    "startled",
    "recovering",
    "gathering",
    "dispersing",
    "stagnant",
    "surging",
    "settled",
    "active",
    "alert",
    "floating",
    "awaiting_consensus",
    "unknown",
]

PresentationEffect = Literal[
    "contract",
    "expand",
    "block",
    "rest",
    "startle",
    "recover",
    "gather",
    "scatter",
    "stagnate",
    "surge",
    "settle",
    "activate",
    "alert",
    "float",
    "hold",
    "verify",
    "echo",
]


class SpecialistPresentation(BaseModel):
    """Deterministic, UI-ready role contribution bound to sealed evidence.

    Provider prose remains available in ``AgentClaim.proposition`` for audit,
    while this compact projection prevents the live UI from guessing meaning
    by parsing free text. Soundscape deliberately has no prose analysis.
    """

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["specialist-presentation.v1"] = (
        "specialist-presentation.v1"
    )
    role: Literal[
        "architecture",
        "biota",
        "feng_shui",
        "psyche",
        "soundscape",
    ]
    contribution: Literal[
        "space_form",
        "space_breath",
        "space_flow",
        "space_tendency",
        "consensus_motion",
    ]
    contribution_label: Literal[
        "看见空间的形",
        "看见空间的息",
        "看见空间的流",
        "看见空间的势",
        "把共识翻译成运动",
    ]
    state: SpecialistPresentationState
    state_label: str = Field(min_length=1, max_length=24)
    analysis: str | None = Field(default=None, max_length=280)
    effect: PresentationEffect

    @model_validator(mode="after")
    def _role_semantics_match(self) -> SpecialistPresentation:
        expected = {
            "architecture": ("space_form", "看见空间的形"),
            "biota": ("space_breath", "看见空间的息"),
            "feng_shui": ("space_flow", "看见空间的流"),
            "psyche": ("space_tendency", "看见空间的势"),
            "soundscape": ("consensus_motion", "把共识翻译成运动"),
        }[self.role]
        if (self.contribution, self.contribution_label) != expected:
            raise ValueError("specialist contribution does not match role")
        if self.role == "soundscape" and self.analysis is not None:
            raise ValueError("soundscape presentation must not contain prose analysis")
        if self.role != "soundscape" and not self.analysis:
            raise ValueError("non-soundscape presentation requires analysis")
        return self


class SkepticAssessment(BaseModel):
    """Explicit evidence decision and one bounded next validation."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["skeptic-assessment.v1"] = "skeptic-assessment.v1"
    evidence_status: Literal["sufficient", "limited", "insufficient"]
    evidence_label: Literal["证据充分", "证据有限", "证据不足"]
    withhold_judgment: bool
    rationale: str = Field(min_length=1, max_length=240)
    next_validation: str = Field(min_length=1, max_length=240)

    @model_validator(mode="after")
    def _label_matches_status(self) -> SkepticAssessment:
        expected = {
            "sufficient": "证据充分",
            "limited": "证据有限",
            "insufficient": "证据不足",
        }[self.evidence_status]
        if self.evidence_label != expected:
            raise ValueError("skeptic evidence label does not match status")
        if self.evidence_status == "insufficient" and not self.withhold_judgment:
            raise ValueError("insufficient evidence must withhold judgment")
        return self


class SoundConsensusMotion(BaseModel):
    """Sound Agent's non-audio translation of the approved Council state."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["sound-consensus-motion.v1"] = (
        "sound-consensus-motion.v1"
    )
    rhythm: Literal["停顿", "缓拍", "稳拍", "急拍", "未知"]
    pitch: Literal["低", "中", "高", "未知"]
    distance: Literal["近", "中", "远", "未知"]
    thickness: Literal["薄", "中", "厚", "未知"]
    synchrony: Literal["松散", "部分同步", "同步", "未知"]


class SpatialLifeInteraction(BaseModel):
    """Fusion's bounded first-person response for the presentation overlay."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["spatial-life-interaction.v1"] = (
        "spatial-life-interaction.v1"
    )
    state: Literal[
        "resting",
        "recovering",
        "gathering",
        "expanding",
        "blocked",
        "surging",
        "floating",
        "waiting",
    ]
    state_label: str = Field(min_length=1, max_length=24)
    message: str = Field(min_length=1, max_length=280)
    wish: str = Field(min_length=1, max_length=240)
    effect: PresentationEffect


class AgentClaim(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "$id": f"{SCHEMA_BASE}/agent_claim.schema.json",
            "title": "AgentClaim",
        },
    )

    schema_version: Literal["agent-claim.v1"] = "agent-claim.v1"
    claim_id: str = Field(min_length=1)
    cycle_id: str = Field(min_length=1)
    agent_id: str = Field(min_length=1)
    agent_version: str = Field(min_length=1)
    role: str = Field(min_length=1)
    lens: Literal["sensor", "metaphor"] = "sensor"
    kind: Literal["observation", "hypothesis", "alternative", "limitation"]
    state: Literal["proposed", "challenged", "revised", "conceded", "withdrawn", "accepted"]
    proposition: str = Field(min_length=1)
    stance: Literal["supports", "contradicts", "neutral"]
    evidence_refs: list[str] = Field(min_length=1)
    counter_evidence_refs: list[str] = Field(default_factory=list)
    sources: list[str] = Field(default_factory=list)
    process: str = Field(default="")
    analysis_steps: list[AnalysisStep] = Field(default_factory=list)
    systematic_reading: SystematicReading | None = None
    continuity: AgentContinuity | None = None
    presentation: SpecialistPresentation | None = None
    assumptions: list[str] = Field(default_factory=list)
    alternative_explanations: list[str] = Field(default_factory=list)
    falsification_test: str = Field(min_length=1)
    reasoning_summary: str = Field(min_length=1)

    @model_validator(mode="after")
    def _presentation_matches_role(self) -> AgentClaim:
        if self.presentation is not None and self.presentation.role != self.role:
            raise ValueError("claim presentation role does not match claim role")
        return self


class AgentChallenge(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "$id": f"{SCHEMA_BASE}/agent_challenge.schema.json",
            "title": "AgentChallenge",
        },
    )

    schema_version: Literal["agent-challenge.v1"] = "agent-challenge.v1"
    challenge_id: str = Field(min_length=1)
    target_claim_id: str = Field(min_length=1)
    challenger_agent_id: str = Field(min_length=1)
    category: Literal[
        "confound",
        "missing_evidence",
        "calibration_mismatch",
        "causal_overreach",
        "contradiction",
        "stale_evidence",
    ]
    proposed_severity: Literal["info", "material", "blocking"]
    statement: str = Field(min_length=1)
    evidence_refs: list[str] = Field(default_factory=list)
    resolution_test: str = Field(min_length=1)
    status: Literal["open", "resolved", "accepted", "rejected_by_policy"]
    continuity: AgentContinuity | None = None
    assessment: SkepticAssessment | None = None


class PolicyRejection(BaseModel):
    """A deterministic arbiter rejection; agents never write these themselves."""

    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "$id": f"{SCHEMA_BASE}/policy_rejection.schema.json",
            "title": "PolicyRejection",
        },
    )

    schema_version: Literal["policy-rejection.v1"] = "policy-rejection.v1"
    rejection_id: str = Field(min_length=1)
    cycle_id: str = Field(min_length=1)
    target_id: str = Field(min_length=1)
    agent_id: str = Field(min_length=1)
    role: AgentRole
    reason_code: str = Field(min_length=1)
    detail: str = Field(min_length=1)
    rejected_at: datetime


class CouncilCallRecord(BaseModel):
    """One provider call (or cache hit), with observable usage only."""

    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "$id": f"{SCHEMA_BASE}/council_call_record.schema.json",
            "title": "CouncilCallRecord",
        },
    )

    schema_version: Literal["council-call.v1"] = "council-call.v1"
    call_id: str = Field(min_length=1)
    cycle_id: str = Field(min_length=1)
    role: AgentRole
    phase: Literal["propose", "cross_examine", "respond", "synthesize"]
    model: str = Field(min_length=1)
    prompt_version: str = Field(min_length=1)
    evidence_hash: str = Field(pattern=HASH_PATTERN)
    status: Literal["ok", "retry", "timeout", "error", "offline", "cache_hit"]
    latency_ms: int = Field(ge=0)
    attempts: int = Field(ge=1)
    input_tokens: int = Field(default=0, ge=0)
    output_tokens: int = Field(default=0, ge=0)
    total_tokens: int = Field(default=0, ge=0)
    trace_id: str | None = None
    error: str | None = None


class AgreementSummary(BaseModel):
    """How many agents agreed; never feeds the confidence formula."""

    model_config = ConfigDict(extra="forbid")

    participants: int = Field(ge=0)
    supporting: int = Field(ge=0)
    contradicting: int = Field(ge=0)
    unresolved_challenges: int = Field(ge=0)
    agreement_ratio: float = Field(ge=0, le=1)

    @model_validator(mode="after")
    def _counts_are_consistent(self) -> AgreementSummary:
        if self.supporting + self.contradicting > self.participants:
            raise ValueError("supporting + contradicting must not exceed participants")
        return self


class Provenance(BaseModel):
    model_config = ConfigDict(extra="forbid")

    contracts_version: str = Field(min_length=1)
    features_version: str = Field(min_length=1)
    calibration_profile_id: str = Field(min_length=1)
    agent_versions: dict[str, str] = Field(default_factory=dict)
    models: dict[str, str] = Field(default_factory=dict)
    policy_version: str = Field(min_length=1)
    generated_at: datetime


class CouncilResult(BaseModel):
    """Final synthesis. display_confidence is bounded by the sensor cap."""

    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "$id": f"{SCHEMA_BASE}/council_result.schema.json",
            "title": "CouncilResult",
        },
    )

    schema_version: Literal["council-result.v1"] = "council-result.v1"
    cycle_id: str = Field(min_length=1)
    evidence_hash: str = Field(pattern=HASH_PATTERN)
    status: Literal["supported", "ambiguous", "unavailable"]
    headline: str = Field(min_length=1)
    summary: str = Field(min_length=1)
    accepted_claim_ids: list[str] = Field(default_factory=list)
    unresolved_challenge_ids: list[str] = Field(default_factory=list)
    alternatives: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    sensor_confidence_cap: float = Field(ge=0, le=1)
    model_support: float = Field(ge=0, le=1)
    display_confidence: float = Field(ge=0, le=1)
    interpretation_agreement: AgreementSummary
    visual_parameters: dict[str, float | str] = Field(default_factory=dict)
    audio_parameters: dict[str, float | str] = Field(default_factory=dict)
    continuity: AgentContinuity | None = None
    sound_motion: SoundConsensusMotion | None = None
    life_interaction: SpatialLifeInteraction | None = None
    action_decision: AgentActionDecision
    provenance: Provenance

    @model_validator(mode="after")
    def _confidence_cap_invariant(self) -> CouncilResult:
        if not (
            0.0
            <= self.display_confidence
            <= self.model_support
            <= self.sensor_confidence_cap
            <= 1.0
        ):
            raise ValueError(
                "final_claim_confidence <= model_support <= sensor_confidence_cap "
                "invariant violated"
            )
        if self.action_decision.cycle_id != self.cycle_id:
            raise ValueError("action decision cycle_id does not match Council result")
        if self.action_decision.evidence_hash != self.evidence_hash:
            raise ValueError("action decision evidence_hash does not match Council result")
        if self.action_decision.sensor_confidence_cap != self.sensor_confidence_cap:
            raise ValueError("action decision sensor cap does not match Council result")
        if self.action_decision.decision_confidence > self.display_confidence:
            raise ValueError(
                "action decision confidence cannot exceed Council display confidence"
            )
        if (
            self.status != "supported"
            and self.action_decision.execution_status != "withheld"
        ):
            raise ValueError(
                "ambiguous or unavailable Council results must withhold action"
            )
        return self


class ProviderHealth(BaseModel):
    """Provider status; never contains credentials."""

    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "$id": f"{SCHEMA_BASE}/provider_health.schema.json",
            "title": "ProviderHealth",
        },
    )

    schema_version: Literal["provider-health.v1"] = "provider-health.v1"
    provider: Literal["mock", "openai", "deepseek"]
    status: Literal["ok", "degraded", "offline"]
    model: str | None = None
    detail: str = Field(min_length=1)
    checked_at: datetime


class CouncilUsageSummary(BaseModel):
    """Aggregate observable call/token usage across completed cycles."""

    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "$id": f"{SCHEMA_BASE}/council_usage_summary.schema.json",
            "title": "CouncilUsageSummary",
        },
    )

    schema_version: Literal["council-usage.v1"] = "council-usage.v1"
    cycles_completed: int = Field(ge=0)
    total_calls: int = Field(ge=0)
    total_attempts: int = Field(ge=0)
    calls_by_role: dict[str, int] = Field(default_factory=dict)
    calls_by_status: dict[str, int] = Field(default_factory=dict)
    total_input_tokens: int = Field(ge=0)
    total_output_tokens: int = Field(ge=0)
    p50_latency_ms: float = Field(ge=0)


class CouncilCycleDetail(BaseModel):
    """Full auditable record of one council cycle (API view)."""

    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "$id": f"{SCHEMA_BASE}/council_cycle_detail.schema.json",
            "title": "CouncilCycleDetail",
        },
    )

    schema_version: Literal["council-cycle.v1"] = "council-cycle.v1"
    cycle_id: str = Field(min_length=1)
    evidence_hash: str = Field(pattern=HASH_PATTERN)
    status: Literal["supported", "ambiguous", "unavailable"]
    phase: Literal[
        "seal",
        "gate",
        "propose",
        "cross_examine",
        "respond",
        "policy",
        "synthesize",
        "commit",
    ]
    started_at: datetime
    finished_at: datetime
    deadline_s: float = Field(ge=0)
    claims: list[AgentClaim] = Field(default_factory=list)
    challenges: list[AgentChallenge] = Field(default_factory=list)
    rejections: list[PolicyRejection] = Field(default_factory=list)
    calls: list[CouncilCallRecord] = Field(default_factory=list)
    result: CouncilResult | None = None
