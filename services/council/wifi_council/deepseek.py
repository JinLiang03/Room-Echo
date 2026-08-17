"""DeepSeek OpenAI-compatible provider with strict Pydantic validation.

DeepSeek JSON Output guarantees JSON syntax, not this application's schema.
Every response is therefore parsed directly into an ``extra='forbid'``
Pydantic model and then rebound to the exact sealed EvidencePacket before it
can enter PolicyArbiter.  Credentials remain server-side.
"""

from __future__ import annotations

import copy
import json
import os
import time
from datetime import UTC, datetime
from typing import Any, Literal, TypeVar, cast

from openai import AsyncOpenAI
from pydantic import BaseModel, ConfigDict, Field
from wifi_contracts import (
    AgentChallenge,
    AgentClaim,
    AgentRole,
    EvidencePacket,
    ProviderHealth,
)

from .config import CouncilConfig, deepseek_model_from_env
from .grounding import (
    build_analysis_steps,
    build_systematic_reading,
    context_refs,
    evidence_ref,
    load_role_knowledge,
    scene_decision,
    stable_index,
)
from .outputs import (
    PERSONAL_SCENE_QUESTION,
    ROLE_LENS_FOCUS,
    AgentChallengeOutput,
    ApprovedCouncilInput,
    ChallengeSet,
    ProxyMeasurementSummary,
    ResponseOutput,
    SpatialLifeReaction,
    SpecialistProposal,
    SynthesisOutput,
)
from .prompts import PromptVersion
from .provider_types import ProviderCall

T = TypeVar("T", bound=BaseModel)


class DeepSeekProposalNarrative(BaseModel):
    """Only the creative text that DeepSeek may contribute to a proposal.

    Measurement state, reactions, evidence refs, role lens, knowledge sources,
    and the save/unknown decision are rebound deterministically on the server.
    Keeping those fields out of the provider schema makes it structurally
    impossible for a model response to mutate the sealed sensing snapshot.
    """

    model_config = ConfigDict(extra="forbid")

    plain_language: str = Field(min_length=1, max_length=160)
    uncertainty: str = Field(min_length=1, max_length=160)
    alternative_explanations: list[str] = Field(default_factory=list, max_length=4)
    falsification_test: str = Field(min_length=1, max_length=200)
    reasoning_summary: str = Field(min_length=1, max_length=200)


class DeepSeekChallengeNarrative(BaseModel):
    """Skeptic wording; target and evidence refs are rebound to this cycle."""

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
    statement: str = Field(min_length=1, max_length=200)
    resolution_test: str = Field(min_length=1, max_length=200)


class DeepSeekChallengeNarratives(BaseModel):
    model_config = ConfigDict(extra="forbid")

    challenges: list[DeepSeekChallengeNarrative] = Field(
        default_factory=list,
        max_length=5,
    )


class DeepSeekSynthesisNarrative(BaseModel):
    """Fusion wording only; sensing and multimodal parameters stay server-owned."""

    model_config = ConfigDict(extra="forbid")

    headline: str = Field(min_length=1, max_length=120)
    plain_language: str = Field(min_length=1, max_length=200)
    action: str = Field(min_length=1, max_length=160)
    uncertainty: str = Field(min_length=1, max_length=160)
    alternatives: list[str] = Field(default_factory=list, max_length=5)
    limitations: list[str] = Field(default_factory=list, max_length=5)


class DeepSeekAgentProvider:
    """Bounded DeepSeek Chat Completions adapter for all Council phases."""

    name = "deepseek"

    def __init__(
        self,
        config: CouncilConfig,
        *,
        api_key: str | None = None,
        model: str | None = None,
        base_url: str | None = None,
    ) -> None:
        self.config = config
        self.api_key = (
            api_key if api_key is not None else os.environ.get("DEEPSEEK_API_KEY")
        )
        self.model = model or deepseek_model_from_env(config)
        self.base_url = (
            base_url
            or os.environ.get("DEEPSEEK_BASE_URL")
            or config.deepseek_base_url
        ).rstrip("/")
        self._cache: dict[tuple[str, ...], ProviderCall[Any]] = {}
        self._client = (
            AsyncOpenAI(api_key=self.api_key, base_url=self.base_url)
            if self.api_key
            else None
        )

    def health(self) -> ProviderHealth:
        if self.api_key:
            return ProviderHealth(
                provider="deepseek",
                status="ok",
                model=self.model,
                detail="configured; network verification requires a completed call",
                checked_at=datetime.now(UTC),
            )
        return ProviderHealth(
            provider="deepseek",
            status="degraded",
            model=self.model,
            detail="no server-side DeepSeek API key",
            checked_at=datetime.now(UTC),
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
        value: T,
        call: ProviderCall[T],
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
                trace_id=cached.trace_id,
            )
        stored = ProviderCall(
            value=copy.deepcopy(value),
            model=self.model,
            latency_ms=call.latency_ms,
            input_tokens=call.input_tokens,
            output_tokens=call.output_tokens,
            trace_id=call.trace_id,
        )
        self._cache[key] = stored
        return stored

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
            trace_id=cached.trace_id,
        )

    @staticmethod
    def _packet_payload(packet: EvidencePacket) -> dict[str, Any]:
        """Return the sealed compact view without leaking a server raw path."""
        return packet.model_dump(mode="json", exclude={"raw_ref"})

    @classmethod
    def _packet_prompt(cls, packet: EvidencePacket) -> str:
        return (
            "当前 sealed EvidencePacket;只读取紧凑代理字段,不读取 raw_ref:\n"
            + json.dumps(cls._packet_payload(packet), ensure_ascii=False)
        )

    @staticmethod
    def _rebind_call(
        call: ProviderCall[Any],
        value: T,
    ) -> ProviderCall[T]:
        """Preserve real-call provenance while replacing only parsed payload."""
        return ProviderCall(
            value=value,
            model=call.model,
            latency_ms=call.latency_ms,
            input_tokens=call.input_tokens,
            output_tokens=call.output_tokens,
            status=call.status,
            cache_hit=call.cache_hit,
            trace_id=call.trace_id,
            error=call.error,
        )

    @staticmethod
    def _ground_proposal(
        narrative: DeepSeekProposalNarrative,
        packet: EvidencePacket,
        role: AgentRole,
    ) -> SpecialistProposal:
        """Bind model wording to server-owned measurement and evidence fields."""
        measurement = ProxyMeasurementSummary.from_packet(packet)
        reaction = SpatialLifeReaction.from_measurement(measurement)
        decision = scene_decision(packet)
        refs = context_refs(packet)
        if decision == "unknown":
            return SpecialistProposal(
                scene_question=PERSONAL_SCENE_QUESTION,
                measurement_summary=measurement,
                reaction=reaction,
                lens_focus=ROLE_LENS_FOCUS[role],
                scene_decision="unknown",
                abstain=True,
                kind="limitation",
                stance="neutral",
                plain_language=narrative.plain_language,
                uncertainty=narrative.uncertainty,
                evidence_refs=refs,
                alternative_explanations=list(narrative.alternative_explanations),
                falsification_test=narrative.falsification_test,
                reasoning_summary=narrative.reasoning_summary,
            )

        knowledge = load_role_knowledge(role)
        entries = knowledge.get("entries", [])
        if not entries:
            raise ValueError(f"knowledge base empty for {role}")
        index = stable_index(packet, role, "deepseek")
        primary = entries[index % len(entries)]
        other = entries[(index + 1) % len(entries)]
        plain_language = narrative.plain_language.strip()
        if "rx-a" in packet.window_summary.links:
            refs.append(evidence_ref(packet, "features/rx-a/temporal_diff_rms"))
        sources = [
            str(entry.get("url", ""))
            for entry in (primary, other)
            if entry.get("url")
        ]
        analysis_steps = build_analysis_steps(
            packet=packet,
            role=role,
            entries=entries,
            primary=primary,
            other=other,
            proposition=plain_language,
        )
        systematic = build_systematic_reading(
            packet=packet,
            role=role,
            entries=entries,
            reaction=reaction,
            proposition=plain_language,
        )
        alternatives = list(narrative.alternative_explanations) or [
            f"另一视角:{other.get('concept', '同一代理组合的其他解释')}",
            "无线干扰或静态布置变化也可能形成相似代理组合",
        ]
        proposal = SpecialistProposal(
            scene_question=PERSONAL_SCENE_QUESTION,
            measurement_summary=measurement,
            reaction=reaction,
            lens_focus=ROLE_LENS_FOCUS[role],
            scene_decision=decision,
            kind="observation",
            stance="supports",
            plain_language=plain_language,
            uncertainty=narrative.uncertainty,
            evidence_refs=refs,
            sources=sources,
            process=(
                "同一问题:是否保存 J 的当前空间节奏;数据路径:"
                "motion|occupancy|depth|quality -> 角色知识映射 -> 受限叙事"
            ),
            analysis_steps=analysis_steps,
            systematic_reading=systematic,
            assumptions=["标定 profile 与当前拓扑匹配", "隐喻解读不等于测量"],
            alternative_explanations=alternatives,
            falsification_test=narrative.falsification_test,
            reasoning_summary=narrative.reasoning_summary,
        )
        assert proposal.systematic_reading is not None
        return proposal.model_copy(
            update={
                "systematic_reading": proposal.systematic_reading.model_copy(
                    update={"headline": proposal.render_proposition()}
                )
            }
        )

    @staticmethod
    def _ground_challenges(
        narratives: DeepSeekChallengeNarratives,
        packet: EvidencePacket,
        claims: list[AgentClaim],
    ) -> ChallengeSet:
        """Keep skeptic wording while binding targets and refs to this cycle."""
        if not claims:
            return ChallengeSet(challenges=[])
        by_id = {claim.claim_id: claim for claim in claims}
        grounded: list[AgentChallengeOutput] = []
        for index, item in enumerate(narratives.challenges):
            target = by_id.get(item.target_claim_id) or claims[index % len(claims)]
            refs = [
                ref
                for ref in target.evidence_refs
                if ref.startswith(f"evidence://{packet.evidence_hash}/")
            ][:4]
            if not refs:
                refs = [evidence_ref(packet, "quality/overall_status")]
            grounded.append(
                AgentChallengeOutput(
                    target_claim_id=target.claim_id,
                    category=item.category,
                    proposed_severity=item.proposed_severity,
                    statement=item.statement,
                    evidence_refs=refs,
                    resolution_test=item.resolution_test,
                )
            )
        if grounded:
            return ChallengeSet(challenges=grounded)
        target = claims[0]
        return ChallengeSet(
            challenges=[
                AgentChallengeOutput(
                    target_claim_id=target.claim_id,
                    category="confound",
                    proposed_severity="material",
                    statement=(
                        "同一代理组合仍可能由无线干扰或静态布置变化形成,"
                        "不能只按当前角色读法解释"
                    ),
                    evidence_refs=[evidence_ref(packet, "quality/overall_status")],
                    resolution_test="保持标定与拓扑不变,对照下一周期是否延续",
                )
            ]
        )

    @staticmethod
    def _ground_synthesis(
        narrative: DeepSeekSynthesisNarrative,
        packet: EvidencePacket,
    ) -> SynthesisOutput:
        measurement = ProxyMeasurementSummary.from_packet(packet)
        return SynthesisOutput(
            measurement_summary=measurement,
            reaction=SpatialLifeReaction.from_measurement(measurement),
            headline=narrative.headline,
            plain_language=narrative.plain_language,
            action=narrative.action,
            uncertainty=narrative.uncertainty,
            alternatives=list(narrative.alternatives),
            limitations=list(narrative.limitations),
            # Empty maps deliberately select FusionAssembler's fixed defaults;
            # the provider never controls the signal-driven visual field.
            visual_parameters={},
            audio_parameters={},
        )

    async def _run_json(
        self,
        *,
        role: AgentRole,
        prompt: PromptVersion,
        output_type: type[T],
        user_input: str,
    ) -> ProviderCall[T]:
        if self._client is None:
            return ProviderCall(
                value=None,
                model=self.model,
                latency_ms=0,
                status="offline",
                error="no DeepSeek API key",
            )
        schema = json.dumps(
            output_type.model_json_schema(),
            ensure_ascii=False,
            separators=(",", ":"),
        )
        scope_notice = ""
        if output_type is DeepSeekProposalNarrative:
            scope_notice = (
                "本次只输出角色叙事字段;measurement_summary、reaction、"
                "scene_question、lens_focus、evidence_refs、analysis_steps 与"
                "systematic_reading 均由服务器根据 sealed packet 回填,不要输出。\n"
            )
        elif output_type is DeepSeekChallengeNarratives:
            scope_notice = (
                "本次只输出质疑叙事与目标 ID;证据引用由服务器绑定,不要输出。\n"
            )
        elif output_type is DeepSeekSynthesisNarrative:
            scope_notice = (
                "本次只输出综合叙事字段;measurement_summary、reaction、"
                "visual_parameters 与 audio_parameters 由服务器回填,不要输出。\n"
            )
        system = (
            f"{prompt.text}\n\n"
            f"{scope_notice}"
            "必须只输出一个 JSON object,不要 Markdown、代码围栏或额外文字。"
            "输出必须严格符合以下 JSON Schema;不得增加字段:\n"
            f"{schema}"
        )
        started = time.perf_counter()
        response = await self._client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user_input},
            ],
            response_format={"type": "json_object"},
            max_tokens=self.config.deepseek_max_output_tokens,
            temperature=0.1,
            stream=False,
            extra_body={"thinking": {"type": "disabled"}},
        )
        latency_ms = int((time.perf_counter() - started) * 1000)
        if not response.choices:
            raise ValueError("DeepSeek returned no choices")
        choice = response.choices[0]
        if choice.finish_reason == "length":
            raise ValueError("DeepSeek JSON response was truncated")
        content = choice.message.content
        if not content or not content.strip():
            raise ValueError("DeepSeek returned empty JSON content")
        value = output_type.model_validate_json(content)
        usage = response.usage
        return ProviderCall(
            value=value,
            model=self.model,
            latency_ms=latency_ms,
            input_tokens=int(usage.prompt_tokens if usage is not None else 0),
            output_tokens=int(usage.completion_tokens if usage is not None else 0),
            trace_id=response.id,
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
        narrative_call = await self._run_json(
            role=role,
            prompt=prompt,
            output_type=DeepSeekProposalNarrative,
            user_input=self._packet_prompt(packet),
        )
        if narrative_call.value is None:
            return cast(ProviderCall[SpecialistProposal], narrative_call)
        proposal = self._ground_proposal(narrative_call.value, packet, role)
        proposal.validate_for(packet, role)
        grounded_call = self._rebind_call(narrative_call, proposal)
        return self._cached(key, proposal, grounded_call)

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
        narrative_call = await self._run_json(
            role="skeptic",
            prompt=prompt,
            output_type=DeepSeekChallengeNarratives,
            user_input=json.dumps(
                {
                    "packet": self._packet_payload(packet),
                    "claims": [claim.model_dump(mode="json") for claim in claims],
                },
                ensure_ascii=False,
            ),
        )
        if narrative_call.value is None:
            return cast(ProviderCall[ChallengeSet], narrative_call)
        challenges = self._ground_challenges(
            narrative_call.value,
            packet,
            claims,
        )
        grounded_call = self._rebind_call(narrative_call, challenges)
        return self._cached(key, challenges, grounded_call)

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
        call = await self._run_json(
            role=role,
            prompt=prompt,
            output_type=ResponseOutput,
            user_input=json.dumps(
                {
                    "packet": self._packet_payload(packet),
                    "claim": claim.model_dump(mode="json"),
                    "challenges": [item.model_dump(mode="json") for item in challenges],
                },
                ensure_ascii=False,
            ),
        )
        if call.value is None:
            return call
        return self._cached(key, call.value, call)

    async def synthesize(
        self,
        approved: ApprovedCouncilInput,
        prompt: PromptVersion,
    ) -> ProviderCall[SynthesisOutput]:
        packet = approved.packet
        key = self._cache_key("fusion", "synthesize", prompt, packet)
        cached = self._cache_lookup(key)
        if cached is not None:
            return cast(ProviderCall[SynthesisOutput], cached)
        narrative_call = await self._run_json(
            role="fusion",
            prompt=prompt,
            output_type=DeepSeekSynthesisNarrative,
            user_input=approved.model_dump_json(),
        )
        if narrative_call.value is None:
            return cast(ProviderCall[SynthesisOutput], narrative_call)
        synthesis = self._ground_synthesis(narrative_call.value, packet)
        synthesis.validate_for(packet)
        grounded_call = self._rebind_call(narrative_call, synthesis)
        return self._cached(key, synthesis, grounded_call)
