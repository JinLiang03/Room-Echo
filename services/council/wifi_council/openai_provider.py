"""Optional OpenAI Agents SDK implementation of the Council provider."""

from __future__ import annotations

import asyncio
import copy
import json
import os
import time
from datetime import UTC, datetime
from typing import Any, TypeVar, cast

from wifi_contracts import (
    AgentChallenge,
    AgentClaim,
    AgentRole,
    EvidencePacket,
    ProviderHealth,
)

from .config import CouncilConfig
from .outputs import (
    ApprovedCouncilInput,
    ChallengeSet,
    ResponseOutput,
    SpecialistProposal,
    SynthesisOutput,
)
from .prompts import PromptVersion
from .provider_types import ProviderCall

T = TypeVar("T")


class OpenAIAgentProvider:
    """OpenAI Agents SDK provider; structured outputs via Pydantic output_type.

    The API key is read only from the server environment. Without a key the
    provider reports degraded health and the orchestrator falls back to the
    mock/baseline — the key never leaves the server and never enters web
    responses or logs.
    """

    name = "openai"

    def __init__(
        self,
        config: CouncilConfig,
        *,
        api_key: str | None = None,
        model: str | None = None,
    ) -> None:
        self.config = config
        self.api_key = api_key if api_key is not None else os.environ.get("OPENAI_API_KEY")
        self.model = model or os.environ.get("AGENT_COUNCIL_MODEL", config.model)
        self._cache: dict[tuple[str, ...], ProviderCall[Any]] = {}
        try:
            from agents import set_tracing_disabled

            set_tracing_disabled(True)
        except Exception:
            pass

    def health(self) -> ProviderHealth:
        now = datetime.now(UTC)
        if self.api_key:
            return ProviderHealth(
                schema_version="provider-health.v1",
                provider="openai",
                status="ok",
                model=self.model,
                detail="configured",
                checked_at=now,
            )
        return ProviderHealth(
            schema_version="provider-health.v1",
            provider="openai",
            status="degraded",
            model=self.model,
            detail="no server-side API key; falling back to mock/baseline",
            checked_at=now,
        )

    def _cache_key(
        self,
        role: AgentRole,
        phase: str,
        prompt: PromptVersion,
        packet: EvidencePacket,
        extra: str = "",
    ) -> tuple[str, ...]:
        return (
            self.name,
            role,
            phase,
            prompt.version,
            prompt.sha256,
            self.model,
            packet.evidence_hash,
            extra,
        )

    def _cached(
        self,
        key: tuple[str, ...],
        value: T | None,
        *,
        input_tokens: int,
        output_tokens: int,
        latency_ms: int,
    ) -> ProviderCall[T]:
        if key in self._cache and self.config.cache_enabled:
            cached = self._cache[key]
            return ProviderCall(
                value=copy.deepcopy(cached.value),
                model=self.model,
                latency_ms=0,
                input_tokens=cached.input_tokens,
                output_tokens=cached.output_tokens,
                status="cache_hit",
                cache_hit=True,
            )
        call = ProviderCall(
            value=copy.deepcopy(value),
            model=self.model,
            latency_ms=latency_ms,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        )
        self._cache[key] = call
        return call

    def _cache_lookup(self, key: tuple[str, ...]) -> ProviderCall[Any] | None:
        if not self.config.cache_enabled or key not in self._cache:
            return None
        cached = self._cache[key]
        return ProviderCall(
            value=copy.deepcopy(cached.value),
            model=self.model,
            latency_ms=0,
            input_tokens=cached.input_tokens,
            output_tokens=cached.output_tokens,
            status="cache_hit",
            cache_hit=True,
        )

    def _packet_prompt(self, packet: EvidencePacket) -> str:
        return (
            "当前 EvidencePacket(sealed,hash="
            f"{packet.evidence_hash}):\n"
            + json.dumps(
                packet.model_dump(mode="json", exclude={"raw_ref"}),
                ensure_ascii=False,
            )
        )

    async def _run_structured(
        self,
        *,
        role: AgentRole,
        prompt: PromptVersion,
        output_type: type[T],
        user_input: str,
    ) -> ProviderCall[T]:
        if not self.api_key:
            return ProviderCall(
                value=None,
                model=self.model,
                latency_ms=0,
                status="offline",
                error="no API key",
            )
        from agents import Agent, Runner

        agent = Agent(
            name=role,
            instructions=prompt.text,
            model=self.model,
            output_type=output_type,
        )
        started = time.perf_counter()
        result = await asyncio.wait_for(
            Runner.run(agent, input=user_input, max_turns=1),
            timeout=self.config.agent_timeout_s,
        )
        latency_ms = int((time.perf_counter() - started) * 1000)
        value = result.final_output
        input_tokens = 0
        output_tokens = 0
        for response in result.raw_responses:
            usage = getattr(response, "usage", None)
            if usage is None:
                continue
            input_tokens += int(getattr(usage, "input_tokens", 0) or 0)
            output_tokens += int(getattr(usage, "output_tokens", 0) or 0)
        if value is None or not isinstance(value, output_type):
            raise ValueError(
                f"provider returned unexpected output type: {type(value).__name__}"
            )
        return ProviderCall(
            value=value,
            model=self.model,
            latency_ms=latency_ms,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        )

    async def propose(
        self,
        role: AgentRole,
        packet: EvidencePacket,
        prompt: PromptVersion,
    ) -> ProviderCall[SpecialistProposal]:
        key = self._cache_key(role, "propose", prompt, packet)
        cached = self._cache_lookup(key)
        if cached is not None:
            return cast(ProviderCall[SpecialistProposal], cached)
        call = await self._run_structured(
            role=role,
            prompt=prompt,
            output_type=SpecialistProposal,
            user_input=self._packet_prompt(packet),
        )
        if call.status == "offline" or call.value is None:
            return call
        call.value.validate_for(packet, role)
        return self._cached(
            key,
            call.value,
            input_tokens=call.input_tokens,
            output_tokens=call.output_tokens,
            latency_ms=call.latency_ms,
        )

    async def challenge(
        self,
        packet: EvidencePacket,
        claims: list[AgentClaim],
        prompt: PromptVersion,
    ) -> ProviderCall[ChallengeSet]:
        key = self._cache_key("skeptic", "cross_examine", prompt, packet)
        cached = self._cache_lookup(key)
        if cached is not None:
            return cast(ProviderCall[ChallengeSet], cached)
        payload = {
            "claims": [claim.model_dump(mode="json") for claim in claims],
            "packet": self._packet_prompt(packet),
        }
        call = await self._run_structured(
            role="skeptic",
            prompt=prompt,
            output_type=ChallengeSet,
            user_input=str(payload),
        )
        if call.status == "offline" or call.value is None:
            return call
        claim_ids = {claim.claim_id for claim in claims}
        if any(
            challenge.target_claim_id not in claim_ids
            for challenge in call.value.challenges
        ):
            raise ValueError("skeptic target_claim_id is not in the current claims")
        return self._cached(
            key,
            call.value,
            input_tokens=call.input_tokens,
            output_tokens=call.output_tokens,
            latency_ms=call.latency_ms,
        )

    async def respond(
        self,
        packet: EvidencePacket,
        claim: AgentClaim,
        challenges: list[AgentChallenge],
        prompt: PromptVersion,
    ) -> ProviderCall[ResponseOutput]:
        role = cast(AgentRole, claim.role)
        key = self._cache_key(role, "respond", prompt, packet, claim.claim_id)
        cached = self._cache_lookup(key)
        if cached is not None:
            return cast(ProviderCall[ResponseOutput], cached)
        payload = {
            "claim": claim.model_dump(mode="json"),
            "challenges": [c.model_dump(mode="json") for c in challenges],
            "packet": self._packet_prompt(packet),
        }
        call = await self._run_structured(
            role=role,
            prompt=prompt,
            output_type=ResponseOutput,
            user_input=str(payload),
        )
        if call.status == "offline" or call.value is None:
            return call
        return self._cached(
            key,
            call.value,
            input_tokens=call.input_tokens,
            output_tokens=call.output_tokens,
            latency_ms=call.latency_ms,
        )

    async def synthesize(
        self,
        approved: ApprovedCouncilInput,
        prompt: PromptVersion,
    ) -> ProviderCall[SynthesisOutput]:
        key = self._cache_key("fusion", "synthesize", prompt, approved.packet)
        cached = self._cache_lookup(key)
        if cached is not None:
            return cast(ProviderCall[SynthesisOutput], cached)
        call = await self._run_structured(
            role="fusion",
            prompt=prompt,
            output_type=SynthesisOutput,
            user_input=approved.model_dump_json(),
        )
        if call.status == "offline" or call.value is None:
            return call
        call.value.validate_for(approved.packet)
        return self._cached(
            key,
            call.value,
            input_tokens=call.input_tokens,
            output_tokens=call.output_tokens,
            latency_ms=call.latency_ms,
        )


__all__ = ["OpenAIAgentProvider"]
