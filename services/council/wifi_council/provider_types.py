"""Shared provider protocol and observable call envelope."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Generic, Literal, Protocol, TypeVar, runtime_checkable

from wifi_contracts import (
    AgentChallenge,
    AgentClaim,
    AgentRole,
    EvidencePacket,
    ProviderHealth,
)

from .outputs import (
    ApprovedCouncilInput,
    ChallengeSet,
    ResponseOutput,
    SpecialistProposal,
    SynthesisOutput,
)
from .prompts import PromptVersion

T = TypeVar("T")
CallStatus = Literal["ok", "timeout", "error", "offline", "cache_hit"]


@dataclass(frozen=True)
class ProviderCall(Generic[T]):
    """One provider attempt with observable usage; never contains secrets."""

    value: T | None
    model: str
    latency_ms: int
    input_tokens: int = 0
    output_tokens: int = 0
    status: CallStatus = "ok"
    cache_hit: bool = False
    trace_id: str | None = None
    error: str | None = None


@runtime_checkable
class AgentProvider(Protocol):
    """Interface from AGENT_COUNCIL.md section 6."""

    name: str
    model: str

    async def propose(
        self,
        role: AgentRole,
        packet: EvidencePacket,
        prompt: PromptVersion,
    ) -> ProviderCall[SpecialistProposal]: ...

    async def challenge(
        self,
        packet: EvidencePacket,
        claims: list[AgentClaim],
        prompt: PromptVersion,
    ) -> ProviderCall[ChallengeSet]: ...

    async def respond(
        self,
        packet: EvidencePacket,
        claim: AgentClaim,
        challenges: list[AgentChallenge],
        prompt: PromptVersion,
    ) -> ProviderCall[ResponseOutput]: ...

    async def synthesize(
        self,
        approved: ApprovedCouncilInput,
        prompt: PromptVersion,
    ) -> ProviderCall[SynthesisOutput]: ...

    def health(self) -> ProviderHealth: ...


__all__ = ["AgentProvider", "CallStatus", "ProviderCall"]
