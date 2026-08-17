"""Pydantic structured outputs returned by providers (Structured Outputs).

These schemas intentionally carry no numeric measurement fields, so an agent
can never add a new value; the PolicyArbiter enforces that text claims do not
quote fabricated measurements either.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator
from wifi_contracts import (
    AgentChallenge,
    AgentClaim,
    AnalysisStep,
    EvidencePacket,
    SystematicReading,
)


class SpecialistProposal(BaseModel):
    model_config = ConfigDict(extra="forbid")

    abstain: bool = False
    kind: Literal["observation", "hypothesis", "alternative", "limitation"] = (
        "observation"
    )
    stance: Literal["supports", "contradicts", "neutral"] = "supports"
    proposition: str = Field(min_length=1)
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


class AgentChallengeOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    target_claim_id: str | None = None
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

    headline: str = Field(min_length=1)
    summary: str = Field(min_length=1)
    alternatives: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    visual_parameters: dict[str, str] = Field(default_factory=dict)
    audio_parameters: dict[str, str] = Field(default_factory=dict)


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
