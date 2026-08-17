"""Pydantic structured outputs returned by providers (Structured Outputs).

These schemas intentionally carry no numeric measurement fields, so an agent
can never add a new value; the PolicyArbiter enforces that text claims do not
quote fabricated measurements either.
"""

from __future__ import annotations

from typing import Final, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator
from wifi_contracts import (
    AgentChallenge,
    AgentClaim,
    AgentRole,
    AnalysisStep,
    EvidencePacket,
    SystematicReading,
)

PERSONAL_SCENE_QUESTION: Final = (
    "对正在小型创作空间工作的 J:当前 motion、occupancy、depth 三个代理和 "
    "quality,是否形成一个值得保存并与下一周期对照的空间节奏时刻?"
)

MotionState = Literal["idle", "micro_motion", "moving", "fast_change", "unknown"]
OccupancyState = Literal["low", "medium", "high", "unknown"]
DepthState = Literal["near", "mid", "far", "unknown"]
QualityState = Literal["ok", "degraded", "insufficient_signal", "uncalibrated"]
MotionReaction = Literal["安静", "轻动", "流动", "躁动", "未知"]
OccupancyReaction = Literal["舒展", "聚拢", "收紧", "未知"]
DepthReaction = Literal["靠近", "停驻", "退后", "未知"]
LensFocus = Literal[
    "spatial_flow",
    "activity_trace",
    "cultural_flow",
    "privacy_reflection",
    "rhythm_field",
]

ROLE_LENS_FOCUS: dict[str, LensFocus] = {
    "architecture": "spatial_flow",
    "biota": "activity_trace",
    "feng_shui": "cultural_flow",
    "psyche": "privacy_reflection",
    "soundscape": "rhythm_field",
}

_REQUIRED_CONTEXT_PATHS = (
    "signals/motion/state",
    "signals/occupancy/state",
    "signals/depth/state",
    "quality/overall_status",
)


def _trim_clause(text: str) -> str:
    value = text.strip()
    while value.endswith(("。", ";")):
        value = value[:-1].rstrip()
    return value


class ProxyMeasurementSummary(BaseModel):
    """Verbatim state labels copied from one sealed EvidencePacket."""

    model_config = ConfigDict(extra="forbid")

    motion: MotionState
    occupancy: OccupancyState
    depth: DepthState
    quality: QualityState

    @classmethod
    def from_packet(cls, packet: EvidencePacket) -> ProxyMeasurementSummary:
        return cls(
            motion=packet.signals.motion.state,
            occupancy=packet.signals.occupancy_density.state,
            depth=packet.signals.depth_zone.state,
            quality=packet.quality.overall_status,
        )

    def render(self) -> str:
        return (
            f"代理数据:活动={self.motion},占用={self.occupancy},"
            f"相对纵深={self.depth},质量={self.quality}"
        )


class SpatialLifeReaction(BaseModel):
    """Controlled narrative verbs; never a claim of actual life or awareness."""

    model_config = ConfigDict(extra="forbid")

    motion: MotionReaction
    occupancy: OccupancyReaction
    depth: DepthReaction

    @classmethod
    def from_measurement(
        cls,
        measurement: ProxyMeasurementSummary,
    ) -> SpatialLifeReaction:
        if measurement.quality in ("insufficient_signal", "uncalibrated"):
            return cls(motion="未知", occupancy="未知", depth="未知")
        motion_map: dict[MotionState, MotionReaction] = {
            "idle": "安静",
            "micro_motion": "轻动",
            "moving": "流动",
            "fast_change": "躁动",
            "unknown": "未知",
        }
        occupancy_map: dict[OccupancyState, OccupancyReaction] = {
            "low": "舒展",
            "medium": "聚拢",
            "high": "收紧",
            "unknown": "未知",
        }
        depth_map: dict[DepthState, DepthReaction] = {
            "near": "靠近",
            "mid": "停驻",
            "far": "退后",
            "unknown": "未知",
        }
        return cls(
            motion=motion_map[measurement.motion],
            occupancy=occupancy_map[measurement.occupancy],
            depth=depth_map[measurement.depth],
        )

    def render(self) -> str:
        return f"{self.motion}、{self.occupancy}、{self.depth}"


class SpecialistProposal(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scene_question: Literal[
        "对正在小型创作空间工作的 J:当前 motion、occupancy、depth 三个代理和 "
        "quality,是否形成一个值得保存并与下一周期对照的空间节奏时刻?"
    ]
    measurement_summary: ProxyMeasurementSummary
    reaction: SpatialLifeReaction
    lens_focus: LensFocus
    scene_decision: Literal["save_candidate", "compare_next", "do_not_save", "unknown"]
    abstain: bool = False
    kind: Literal["observation", "hypothesis", "alternative", "limitation"] = (
        "observation"
    )
    stance: Literal["supports", "contradicts", "neutral"] = "supports"
    plain_language: str = Field(min_length=1, max_length=160)
    uncertainty: str = Field(min_length=1, max_length=160)
    evidence_refs: list[str] = Field(default_factory=list)
    counter_evidence_refs: list[str] = Field(default_factory=list)
    sources: list[str] = Field(default_factory=list)
    process: str = Field(default="")
    analysis_steps: list[AnalysisStep] = Field(default_factory=list)
    systematic_reading: SystematicReading | None = None
    assumptions: list[str] = Field(default_factory=list)
    alternative_explanations: list[str] = Field(default_factory=list)
    falsification_test: str = Field(min_length=1)
    reasoning_summary: str = Field(min_length=1)

    @model_validator(mode="after")
    def _require_current_context(self) -> SpecialistProposal:
        missing = [
            path
            for path in _REQUIRED_CONTEXT_PATHS
            if not any(ref.endswith(f"/{path}") for ref in self.evidence_refs)
        ]
        if missing:
            raise ValueError(
                "proposal must reference current motion/occupancy/depth/quality: "
                + ", ".join(missing)
            )
        expected_reaction = SpatialLifeReaction.from_measurement(
            self.measurement_summary
        )
        if self.reaction != expected_reaction:
            raise ValueError("reaction must be derived from measurement_summary")
        if self.abstain and self.scene_decision != "unknown":
            raise ValueError("abstain proposals require scene_decision=unknown")
        if not self.abstain:
            if self.systematic_reading is None:
                raise ValueError("non-abstain proposals require systematic_reading")
            signals = [layer.signal for layer in self.systematic_reading.layers]
            if signals != ["motion", "occupancy", "depth"]:
                raise ValueError(
                    "systematic_reading must cover motion, occupancy, depth in order"
                )
        return self

    def validate_for(self, packet: EvidencePacket, role: AgentRole) -> None:
        """Bind provider output to the exact packet and expected role lens."""
        expected_measurement = ProxyMeasurementSummary.from_packet(packet)
        if self.measurement_summary != expected_measurement:
            raise ValueError("measurement_summary does not match current EvidencePacket")
        if self.reaction != SpatialLifeReaction.from_measurement(expected_measurement):
            raise ValueError("reaction does not match current EvidencePacket")
        expected_focus = ROLE_LENS_FOCUS.get(role)
        if expected_focus is None or self.lens_focus != expected_focus:
            raise ValueError(f"lens_focus does not match role {role}")

    def render_proposition(self) -> str:
        decision = {
            "save_candidate": "保存为节奏候选并对照下一周期",
            "compare_next": "先对照下一周期再判断",
            "do_not_save": "暂不保存为节奏结论",
            "unknown": "保持未知",
        }[self.scene_decision]
        plain = _trim_clause(self.plain_language)
        uncertainty = _trim_clause(self.uncertainty)
        return (
            f"{self.measurement_summary.render()};"
            "空间生命体反应(叙事隐喻,不表示真实生命或意识):"
            f"{self.reaction.render()};{plain};建议:{decision};"
            f"限制:{uncertainty}。"
        )


class AgentChallengeOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    target_claim_id: str = Field(min_length=1)
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


class ChallengeSet(BaseModel):
    model_config = ConfigDict(extra="forbid")

    challenges: list[AgentChallengeOutput] = Field(default_factory=list)


class ResponseOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    state: Literal["revised", "conceded", "withdrawn"]
    proposition: str | None = None
    alternative_explanations: list[str] = Field(default_factory=list)
    falsification_test: str | None = None
    reasoning_summary: str = Field(min_length=1)

    @model_validator(mode="after")
    def _revised_requires_proposition(self) -> ResponseOutput:
        if self.state == "revised" and not self.proposition:
            raise ValueError("revised responses require a proposition")
        return self


class SynthesisOutput(BaseModel):
    """Fusion output: narrative and *predefined mapping keys* only."""

    model_config = ConfigDict(extra="forbid")

    measurement_summary: ProxyMeasurementSummary
    reaction: SpatialLifeReaction
    headline: str = Field(min_length=1)
    plain_language: str = Field(min_length=1, max_length=200)
    action: str = Field(min_length=1, max_length=160)
    uncertainty: str = Field(min_length=1, max_length=160)
    alternatives: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    visual_parameters: dict[str, str] = Field(default_factory=dict)
    audio_parameters: dict[str, str] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _reaction_matches_measurement(self) -> SynthesisOutput:
        expected = SpatialLifeReaction.from_measurement(self.measurement_summary)
        if self.reaction != expected:
            raise ValueError("reaction must be derived from measurement_summary")
        return self

    def validate_for(self, packet: EvidencePacket) -> None:
        expected = ProxyMeasurementSummary.from_packet(packet)
        if self.measurement_summary != expected:
            raise ValueError("fusion measurement_summary does not match EvidencePacket")
        if self.reaction != SpatialLifeReaction.from_measurement(expected):
            raise ValueError("fusion reaction does not match EvidencePacket")

    def render_summary(self) -> str:
        plain = _trim_clause(self.plain_language)
        action = _trim_clause(self.action)
        uncertainty = _trim_clause(self.uncertainty)
        return (
            f"{self.measurement_summary.render()};"
            "空间生命体反应(叙事隐喻,不表示真实生命或意识):"
            f"{self.reaction.render()};{plain};建议:{action};"
            f"限制:{uncertainty}。"
        )


class ApprovedCouncilInput(BaseModel):
    """Everything Fusion may read; numbers are copied verbatim from here."""

    model_config = ConfigDict(extra="forbid")

    packet: EvidencePacket
    claims: list[AgentClaim] = Field(default_factory=list)
    challenges: list[AgentChallenge] = Field(default_factory=list)
    status: Literal["supported", "ambiguous", "unavailable"]
    sensor_confidence_cap: float = Field(ge=0, le=1)
    model_support: float = Field(ge=0, le=1)
    display_confidence: float = Field(ge=0, le=1)
