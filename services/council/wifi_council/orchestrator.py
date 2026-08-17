"""Council orchestrator: the auditable debate state machine.

State machine per AGENT_COUNCIL.md section 5: seal -> gate -> propose ->
cross_examine -> respond -> policy -> synthesize -> commit. The default call
budget is 10; retries count toward the budget, and a 15 s hard deadline bounds
each streaming cycle so the signal UI never waits on an LLM call.
"""

from __future__ import annotations

import asyncio
import hashlib
import time
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any, Literal, cast

from wifi_contracts import (
    AgentChallenge,
    AgentClaim,
    AgentContinuity,
    AgentRole,
    AgreementSummary,
    AnalysisStep,
    CouncilCallRecord,
    CouncilCycleDetail,
    CouncilResult,
    EvidencePacket,
    Provenance,
)

from .actions import build_agent_action_decision
from .config import CouncilConfig
from .continuity import ContinuityContext, CouncilContinuityTracker
from .fusion import DEFAULT_AUDIO, DEFAULT_VISUAL, FusionAssembler
from .outputs import (
    ApprovedCouncilInput,
    ProxyMeasurementSummary,
    SpatialLifeReaction,
    SpecialistProposal,
    SynthesisOutput,
)
from .policy import PolicyArbiter
from .presentation import (
    build_skeptic_assessment,
    build_sound_consensus_motion,
    build_spatial_life_interaction,
    build_specialist_presentation,
)
from .prompts import PromptVersion, prompt_registry
from .provider_types import AgentProvider, ProviderCall

PROPOSE_ROLES: tuple[AgentRole, ...] = (
    "architecture",
    "biota",
    "feng_shui",
    "psyche",
    "soundscape",
)

ProgressSink = Callable[[str, dict[str, Any]], None]


class CouncilBudget:
    def __init__(self, max_calls: int) -> None:
        self.max_calls = max_calls
        self.used = 0

    @property
    def remaining(self) -> int:
        return max(0, self.max_calls - self.used)

    def can_spend(self, attempts: int = 1) -> bool:
        return self.used + attempts <= self.max_calls

    def spend(self, attempts: int) -> None:
        self.used += attempts


def baseline_result(
    packet: EvidencePacket,
    *,
    status: Literal["supported", "ambiguous", "unavailable"],
    headline: str,
    summary: str,
    model_support: float = 0.0,
    display_confidence: float = 0.0,
    limitations: list[str] | None = None,
    generated_at: datetime | None = None,
    features_version: str = "features-v2",
) -> CouncilResult:
    generated_at = generated_at or datetime.now(UTC)
    agreement = AgreementSummary(
        participants=0,
        supporting=0,
        contradicting=0,
        unresolved_challenges=0,
        agreement_ratio=0.0,
    )
    return CouncilResult(
        schema_version="council-result.v1",
        cycle_id=packet.cycle_id,
        evidence_hash=packet.evidence_hash,
        status=status,
        headline=headline,
        summary=summary,
        sensor_confidence_cap=packet.signals.sensor_confidence_cap,
        model_support=model_support,
        display_confidence=display_confidence,
        interpretation_agreement=agreement,
        visual_parameters=dict(DEFAULT_VISUAL),
        audio_parameters=dict(DEFAULT_AUDIO),
        sound_motion=build_sound_consensus_motion(
            packet,
            agreement,
            status=status,
        ),
        life_interaction=build_spatial_life_interaction(
            packet,
            status=status,
            provider_message=summary,
            provider_action="保留当前快照并等待下一周期",
        ),
        action_decision=build_agent_action_decision(
            packet,
            status=status,
            decision_confidence=display_confidence,
            decided_at=generated_at,
        ),
        limitations=limitations or ["代理信号,非影像、非人数、非米制距离"],
        provenance=Provenance(
            contracts_version="1.0.0",
            features_version=features_version,
            calibration_profile_id=packet.calibration.calibration_profile_id,
            models={},
            policy_version="policy-v1",
            generated_at=generated_at,
        ),
    )


class CouncilOrchestrator:
    def __init__(
        self,
        provider: AgentProvider,
        config: CouncilConfig,
        *,
        policy: PolicyArbiter | None = None,
        fusion: FusionAssembler | None = None,
        prompts: dict[AgentRole, PromptVersion] | None = None,
        features_version: str = "features-v2",
        propose_roles: tuple[AgentRole, ...] | None = None,
        continuity: CouncilContinuityTracker | None = None,
        progress_sink: ProgressSink | None = None,
    ) -> None:
        self.provider = provider
        self.config = config
        self.policy = policy or PolicyArbiter(config)
        self.fusion = fusion or FusionAssembler(config)
        self.prompts = prompts or prompt_registry()
        self.features_version = features_version
        self.propose_roles = propose_roles or PROPOSE_ROLES
        self.continuity = continuity or CouncilContinuityTracker()
        self.progress_sink = progress_sink

    def set_progress_sink(self, sink: ProgressSink | None) -> None:
        """Attach a non-blocking presentation sink owned by the stream runtime."""
        self.progress_sink = sink

    def reset_continuity(self, session_id: str | None = None) -> None:
        """Drop presentation memory after a replay seek or session reset."""
        self.continuity.reset(session_id)

    def _emit_progress(self, event_type: str, payload: dict[str, Any]) -> None:
        if self.progress_sink is None:
            return
        try:
            self.progress_sink(event_type, payload)
        except Exception:
            # Presentation observers must never fail or delay Council execution.
            return

    @staticmethod
    def _contextual_prompt(
        prompt: PromptVersion,
        context: ContinuityContext,
    ) -> PromptVersion:
        appendix = context.prompt_appendix()
        text = f"{prompt.text}\n\n{appendix}"
        digest = "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest()
        return prompt.model_copy(
            update={
                "version": f"{prompt.version}+continuity.v1",
                "sha256": digest,
                "text": text,
            }
        )

    # ---- provider call helper ------------------------------------------

    async def _call_with_retry(
        self,
        fn: Any,
        *args: Any,
        role: AgentRole,
        phase: Literal["propose", "cross_examine", "respond", "synthesize"],
        packet: EvidencePacket,
        prompt: PromptVersion,
        max_attempts: int | None = None,
        attempt_offset: int = 0,
    ) -> tuple[ProviderCall[Any] | None, list[CouncilCallRecord]]:
        records: list[CouncilCallRecord] = []
        last: ProviderCall[Any] | None = None
        attempts = 0
        allowed_attempts = max_attempts or self.config.retry_attempts
        while attempts < allowed_attempts:
            attempts += 1
            attempt_number = attempt_offset + attempts
            started = time.perf_counter()
            try:
                last = await asyncio.wait_for(
                    fn(*args),
                    timeout=self.config.agent_timeout_s,
                )
            except TimeoutError:
                last = ProviderCall(
                    value=None,
                    model=self.provider.model,
                    latency_ms=int((time.perf_counter() - started) * 1000),
                    status="timeout",
                    error="agent timeout",
                )
            except Exception as exc:  # provider/parse failures are audited
                last = ProviderCall(
                    value=None,
                    model=self.provider.model,
                    latency_ms=int((time.perf_counter() - started) * 1000),
                    status="error",
                    error=str(exc)[:200],
                )
            assert last is not None
            records.append(
                CouncilCallRecord(
                    schema_version="council-call.v1",
                    call_id=(
                        f"call-{packet.cycle_id}-{phase}-{role}-{attempt_number}"
                    ),
                    cycle_id=packet.cycle_id,
                    role=role,
                    phase=phase,
                    model=last.model,
                    prompt_version=prompt.version,
                    evidence_hash=packet.evidence_hash,
                    status=last.status,
                    latency_ms=last.latency_ms,
                    attempts=attempt_number,
                    input_tokens=last.input_tokens,
                    output_tokens=last.output_tokens,
                    total_tokens=last.input_tokens + last.output_tokens,
                    trace_id=last.trace_id,
                    error=last.error,
                )
            )
            if last.status in ("ok", "cache_hit") and last.value is not None:
                return last, records
            if last.status == "offline":
                return last, records
        return last, records

    # ---- claims ---------------------------------------------------------

    def _claim_from_proposal(
        self,
        packet: EvidencePacket,
        proposal: SpecialistProposal,
        role: AgentRole,
        claim_seq: int,
        continuity: AgentContinuity,
    ) -> AgentClaim:
        agent_version = getattr(self.provider, "template_version", self.prompts[role].version)
        proposition = proposal.render_proposition()
        systematic_reading = proposal.systematic_reading
        if systematic_reading is not None:
            systematic_reading = systematic_reading.model_copy(
                update={"headline": proposition}
            )
        analysis_steps = list(proposal.analysis_steps)
        analysis_steps.insert(
            1 if analysis_steps else 0,
            AnalysisStep(
                step_id="compare",
                phase="compare",
                title="对照上一周期",
                text=continuity.summary,
                evidence_refs=[],
            ),
        )
        return AgentClaim(
            schema_version="agent-claim.v1",
            claim_id=f"claim-{packet.cycle_id}-{claim_seq:02d}",
            cycle_id=packet.cycle_id,
            agent_id=f"agent-{role}-{claim_seq:02d}",
            agent_version=agent_version,
            role=role,
            lens="metaphor",
            kind=proposal.kind,
            state="proposed",
            proposition=proposition,
            stance=proposal.stance,
            evidence_refs=list(proposal.evidence_refs),
            counter_evidence_refs=list(proposal.counter_evidence_refs),
            sources=list(proposal.sources),
            process=proposal.process,
            analysis_steps=analysis_steps,
            systematic_reading=systematic_reading,
            continuity=continuity,
            presentation=build_specialist_presentation(packet, role, continuity),
            assumptions=list(proposal.assumptions),
            alternative_explanations=list(proposal.alternative_explanations),
            falsification_test=proposal.falsification_test,
            reasoning_summary=proposal.reasoning_summary,
        )

    # ---- auto cross-review (deterministic safety net) -------------------

    def _auto_cross_review(
        self,
        packet: EvidencePacket,
        claims: list[AgentClaim],
    ) -> list[AgentChallenge]:
        challenges: list[AgentChallenge] = []
        seq = 0
        for claim in claims:
            if claim.stance != "supports":
                continue
            refs = " ".join([*claim.evidence_refs, *claim.counter_evidence_refs])
            sensor_unknown = (
                "signals/motion" in refs and packet.signals.motion.state == "unknown"
            ) or (
                "signals/occupancy" in refs
                and packet.signals.occupancy_density.state == "unknown"
            ) or (
                "signals/depth" in refs
                and packet.signals.depth_zone.state == "unknown"
            )
            if sensor_unknown:
                seq += 1
                challenges.append(
                    AgentChallenge(
                        schema_version="agent-challenge.v1",
                        challenge_id=f"challenge-{packet.cycle_id}-auto-{seq:02d}",
                        target_claim_id=claim.claim_id,
                        challenger_agent_id="policy-cross-review",
                        category="stale_evidence",
                        proposed_severity="blocking",
                        statement="主张的 present 状态与传感器 unknown 冲突. ",
                        evidence_refs=[
                            f"evidence://{packet.evidence_hash}/quality/overall_status"
                        ],
                        resolution_test="等待新的非 unknown 窗口. ",
                        status="open",
                    )
                )
            if (
                "signals/depth" in refs
                and not packet.topology.depth_output_allowed
            ):
                seq += 1
                challenges.append(
                    AgentChallenge(
                        schema_version="agent-challenge.v1",
                        challenge_id=f"challenge-{packet.cycle_id}-auto-{seq:02d}",
                        target_claim_id=claim.claim_id,
                        challenger_agent_id="policy-cross-review",
                        category="causal_overreach",
                        proposed_severity="blocking",
                        statement="单 RX 拓扑不支持纵深解读. ",
                        evidence_refs=[
                            f"evidence://{packet.evidence_hash}/topology/depth_output_allowed"
                        ],
                        resolution_test="接入第二个非共线 RX 并重标定. ",
                        status="open",
                    )
                )
        return challenges[: self.config.max_challenges_total]

    # ---- main cycle -----------------------------------------------------

    async def run_cycle(
        self,
        packet: EvidencePacket,
        *,
        now: datetime | None = None,
    ) -> CouncilCycleDetail:
        now = now or datetime.now(UTC)
        budget = CouncilBudget(self.config.max_calls_per_cycle)
        calls: list[CouncilCallRecord] = []
        claims: list[AgentClaim] = []
        challenges: list[AgentChallenge] = []
        responded_claim_ids: set[str] = set()
        result: CouncilResult | None = None
        phase: Literal[
            "seal",
            "gate",
            "propose",
            "cross_examine",
            "respond",
            "policy",
            "synthesize",
            "commit",
        ] = "seal"

        def make_detail() -> CouncilCycleDetail:
            return CouncilCycleDetail(
                schema_version="council-cycle.v1",
                cycle_id=packet.cycle_id,
                evidence_hash=packet.evidence_hash,
                status=result.status if result else "unavailable",
                phase=phase,
                started_at=now,
                finished_at=datetime.now(UTC),
                deadline_s=self.config.cycle_deadline_s,
                claims=claims,
                challenges=challenges,
                rejections=[],
                calls=calls,
                result=result,
            )

        # 1. seal
        if not packet.verify_integrity():
            result = baseline_result(
                packet,
                status="unavailable",
                headline="证据封存校验失败",
                summary="EvidencePacket hash 不匹配;拒绝推理. ",
                limitations=["证据完整性校验失败"],
                generated_at=now,
            )
            phase = "commit"
            return make_detail()

        continuity_contexts = {
            role: self.continuity.context(packet, role)
            for role in (*self.propose_roles, "skeptic", "fusion")
        }
        cycle_prompts = {
            role: self._contextual_prompt(self.prompts[role], context)
            for role, context in continuity_contexts.items()
        }

        # 2. gate — no inference when the deterministic quality gate fails.
        if packet.signals.status in ("insufficient_signal", "uncalibrated"):
            phase = "gate"
            result = baseline_result(
                packet,
                status="unavailable",
                headline="质量门未通过,无推理",
                summary=(
                    "信号状态 "
                    f"{packet.signals.status};不提供 presence 解读. "
                ),
                limitations=["质量门未通过(不运行 Agent)"],
                generated_at=now,
            )
            result = result.model_copy(
                update={"continuity": continuity_contexts["fusion"].record}
            )
            phase = "commit"
            detail = make_detail()
            self.continuity.commit(packet, claims, challenges, result)
            return detail

        # 3. propose — one bounded parallel fan-out, then budget-aware retries.
        phase = "propose"
        active_roles = self.propose_roles[: budget.remaining]

        async def propose_once(
            role: AgentRole,
            *,
            attempt_offset: int = 0,
        ) -> tuple[AgentRole, ProviderCall[Any] | None, list[CouncilCallRecord]]:
            prompt = cycle_prompts[role]
            call, records = await self._call_with_retry(
                self.provider.propose,
                role,
                packet,
                prompt,
                role=role,
                phase="propose",
                packet=packet,
                prompt=prompt,
                max_attempts=1,
                attempt_offset=attempt_offset,
            )
            return role, call, records

        first_wave = await asyncio.gather(
            *(propose_once(role) for role in active_roles)
        )
        proposal_calls: dict[AgentRole, ProviderCall[Any] | None] = {}
        for role, call, records in first_wave:
            calls.extend(records)
            budget.spend(len(records))
            proposal_calls[role] = call

        failed_roles = [
            role
            for role in active_roles
            if proposal_calls.get(role) is None
            or proposal_calls[role].value is None  # type: ignore[union-attr]
        ]
        # Keep two calls reserved for skeptic + fusion. With a larger explicit
        # budget, failed specialists receive one concurrent retry.
        retry_capacity = max(0, budget.remaining - 2)
        retry_roles = failed_roles[:retry_capacity]
        if retry_roles and self.config.retry_attempts > 1:
            retry_wave = await asyncio.gather(
                *(propose_once(role, attempt_offset=1) for role in retry_roles)
            )
            for role, call, records in retry_wave:
                calls.extend(records)
                budget.spend(len(records))
                proposal_calls[role] = call

        for claim_seq, role in enumerate(self.propose_roles, start=1):
            call = proposal_calls.get(role)
            if call is None or call.value is None:
                continue
            claim = self._claim_from_proposal(
                packet,
                call.value,
                role,
                claim_seq,
                continuity_contexts[role].record,
            )
            claims.append(claim)
            precheck = self.policy.arbitrate(packet, [claim], [], now=now)
            if precheck.accepted_claims:
                self._emit_progress(
                    "agent.claim",
                    {
                        "cycle_id": packet.cycle_id,
                        "claim": claim.model_dump(mode="json"),
                    },
                )

        if calls and not claims and all(record.status == "timeout" for record in calls):
            result = baseline_result(
                packet,
                status="ambiguous",
                headline="讨论超时",
                summary="Provider 提案调用均超过单次时限;保留确定性传感器摘要。",
                model_support=min(
                    packet.signals.motion.confidence,
                    packet.signals.occupancy_density.confidence,
                    packet.signals.depth_zone.confidence,
                    packet.signals.sensor_confidence_cap,
                ),
                display_confidence=0.0,
                limitations=["all_proposer_calls_timed_out"],
                generated_at=now,
            ).model_copy(
                update={"continuity": continuity_contexts["fusion"].record}
            )
            phase = "commit"
            detail = make_detail()
            self.continuity.commit(packet, claims, challenges, result)
            return detail

        # 4. cross-examine: RedTeam + deterministic auto cross-review
        phase = "cross_examine"
        if claims and budget.can_spend():
            prompt = cycle_prompts["skeptic"]
            call, records = await self._call_with_retry(
                self.provider.challenge,
                packet,
                claims,
                prompt,
                role="skeptic",
                phase="cross_examine",
                packet=packet,
                prompt=prompt,
                max_attempts=min(self.config.retry_attempts, budget.remaining),
            )
            calls.extend(records)
            budget.spend(len(records))
            if call is not None and call.value is not None:
                for seq, output in enumerate(call.value.challenges, start=1):
                    challenges.append(
                        AgentChallenge(
                            schema_version="agent-challenge.v1",
                            challenge_id=f"challenge-{packet.cycle_id}-{seq:02d}",
                            target_claim_id=output.target_claim_id,
                            challenger_agent_id=f"agent-skeptic-{seq:02d}",
                            category=output.category,
                            proposed_severity=output.proposed_severity,
                            statement=output.statement,
                            evidence_refs=list(output.evidence_refs),
                            resolution_test=output.resolution_test,
                            status="open",
                            continuity=continuity_contexts["skeptic"].record,
                        )
                    )
        challenges.extend(self._auto_cross_review(packet, claims))
        for challenge in challenges:
            if challenge.continuity is None:
                challenge.continuity = continuity_contexts["skeptic"].record

        # 5. respond: deterministic priority (blocking first), budget allowing
        phase = "respond"
        claim_by_id = {claim.claim_id: claim for claim in claims}
        active_claims = {claim.claim_id for claim in claims}
        for challenge in sorted(
            challenges,
            key=lambda item: (
                0 if item.proposed_severity == "blocking" else 1,
                item.target_claim_id,
            ),
        ):
            if challenge.status != "open":
                continue
            target = claim_by_id.get(challenge.target_claim_id)
            if target is None or target.claim_id not in active_claims:
                continue
            # Always preserve one bounded call for Fusion synthesis.
            if budget.remaining <= 1:
                break
            claim_challenges = [
                item for item in challenges if item.target_claim_id == target.claim_id
            ]
            claim_role = cast(AgentRole, target.role)
            prompt = cycle_prompts[claim_role]
            call, records = await self._call_with_retry(
                self.provider.respond,
                packet,
                target,
                claim_challenges,
                prompt,
                role=claim_role,
                phase="respond",
                packet=packet,
                prompt=prompt,
                max_attempts=min(
                    self.config.retry_attempts,
                    budget.remaining - 1,
                ),
            )
            calls.extend(records)
            budget.spend(len(records))
            if call is None or call.value is None:
                continue
            response = call.value
            if response.state == "conceded":
                target.state = "conceded"
                for item in claim_challenges:
                    item.status = "accepted"
                active_claims.discard(target.claim_id)
            elif response.state == "withdrawn":
                target.state = "withdrawn"
                for item in claim_challenges:
                    item.status = "resolved"
                active_claims.discard(target.claim_id)
            else:
                target.state = "revised"
                if response.proposition:
                    target.proposition = response.proposition
                target.falsification_test = (
                    response.falsification_test or target.falsification_test
                )
                target.alternative_explanations = list(
                    response.alternative_explanations
                ) or target.alternative_explanations
                for item in claim_challenges:
                    item.status = "resolved"
            # Do not stream a provider revision before the full deterministic
            # policy pass. An invalid response must never flash in the UI.
            responded_claim_ids.add(target.claim_id)

        # 6. policy
        phase = "policy"
        verdict = self.policy.arbitrate(packet, claims, challenges, now=now)
        assessment_by_id = {
            challenge.challenge_id: build_skeptic_assessment(packet, challenge)
            for challenge in verdict.challenges
        }
        for challenge in [*challenges, *verdict.challenges]:
            assessment = assessment_by_id.get(challenge.challenge_id)
            if assessment is not None:
                challenge.assessment = assessment
        for challenge in verdict.challenges:
            self._emit_progress(
                "agent.challenge",
                {
                    "cycle_id": packet.cycle_id,
                    "challenge": challenge.model_dump(mode="json"),
                },
            )
        for rejection in verdict.rejections:
            self._emit_progress(
                "policy.rejection",
                {
                    "cycle_id": packet.cycle_id,
                    "rejection": rejection.model_dump(mode="json"),
                },
            )
        rejected_target_ids = {item.target_id for item in verdict.rejections}
        safe_challenges = [
            item
            for item in verdict.challenges
            if item.challenge_id not in rejected_target_ids
        ]
        for claim in claims:
            if (
                claim.claim_id not in responded_claim_ids
                or claim.claim_id in rejected_target_ids
            ):
                continue
            self._emit_progress(
                "agent.response",
                {
                    "cycle_id": packet.cycle_id,
                    "claim": claim.model_dump(mode="json"),
                    "challenges": [
                        item.model_dump(mode="json")
                        for item in safe_challenges
                        if item.target_claim_id == claim.claim_id
                    ],
                },
            )

        # 7. synthesize: provider fusion only when validated and budget allows
        phase = "synthesize"
        synthesis: SynthesisOutput | None = None
        all_offline = bool(calls) and all(
            record.status == "offline" for record in calls
        )
        if verdict.accepted_claims and budget.can_spend() and not all_offline:
            approved = ApprovedCouncilInput(
                packet=packet,
                claims=verdict.accepted_claims,
                challenges=verdict.unresolved_challenges,
                status=verdict.status,
                sensor_confidence_cap=packet.signals.sensor_confidence_cap,
                model_support=verdict.model_support,
                display_confidence=verdict.display_confidence,
            )
            prompt = cycle_prompts["fusion"]
            call, records = await self._call_with_retry(
                self.provider.synthesize,
                approved,
                prompt,
                role="fusion",
                phase="synthesize",
                packet=packet,
                prompt=prompt,
                max_attempts=min(self.config.retry_attempts, budget.remaining),
            )
            calls.extend(records)
            budget.spend(len(records))
            if call is not None and call.value is not None:
                synthesis_rejections = self.policy.validate_synthesis(
                    packet,
                    call.value,
                    verdict,
                    now=now,
                )
                if not synthesis_rejections:
                    synthesis = call.value
                else:
                    for rejection in synthesis_rejections:
                        rejection.rejection_id = (
                            f"rejection-{packet.cycle_id}-synth"
                        )
                        verdict.rejections.append(rejection)

        if all_offline:
            measurement = ProxyMeasurementSummary.from_packet(packet)
            synthesis = SynthesisOutput(
                measurement_summary=measurement,
                reaction=SpatialLifeReaction.from_measurement(measurement),
                headline="讨论不可用",
                plain_language="真实 Agent provider 离线,未生成角色解释",
                action="保留当前代理快照并稍后重试",
                uncertainty="当前只有确定性代理数据,没有真实模型结论",
                limitations=["provider offline;无 Agent 输出"],
                visual_parameters=dict(DEFAULT_VISUAL),
                audio_parameters=dict(DEFAULT_AUDIO),
            )

        provider_models: dict[str, str] = {
            str(role): self.provider.model
            for role in (*self.propose_roles, "skeptic", "fusion")
            if any(record.role == role for record in calls)
        }
        result = self.fusion.assemble(
            packet,
            verdict,
            synthesis=synthesis,
            features_version=self.features_version,
            prompt_version=cycle_prompts["fusion"].version,
            provider_models=provider_models,
            generated_at=now,
        )
        result = result.model_copy(
            update={"continuity": continuity_contexts["fusion"].record}
        )

        # 8. commit
        phase = "commit"
        detail = CouncilCycleDetail(
            schema_version="council-cycle.v1",
            cycle_id=packet.cycle_id,
            evidence_hash=packet.evidence_hash,
            status=result.status,
            phase=phase,
            started_at=now,
            finished_at=datetime.now(UTC),
            deadline_s=self.config.cycle_deadline_s,
            claims=claims,
            challenges=challenges,
            rejections=verdict.rejections,
            calls=calls,
            result=result,
        )
        # Only policy-screened records may become next-cycle prompt context.
        # Rejected provider text remains in the audit detail but cannot poison
        # future role memory.
        self.continuity.commit(
            packet,
            verdict.accepted_claims,
            verdict.challenges,
            result,
        )
        return detail

    async def deadline_result(
        self,
        packet: EvidencePacket,
        *,
        elapsed_s: float,
        now: datetime | None = None,
    ) -> CouncilCycleDetail:
        """15 s hard deadline fallback: auditable, degraded, deterministic."""
        now = now or datetime.now(UTC)
        result = baseline_result(
            packet,
            status="ambiguous",
            headline="讨论超时",
            summary="Council 周期超过硬性时限;保留确定性传感器摘要. ",
            model_support=min(
                packet.signals.motion.confidence,
                packet.signals.occupancy_density.confidence,
                packet.signals.depth_zone.confidence,
            ),
            display_confidence=0.0,
            limitations=["cycle_deadline_exceeded"],
            generated_at=now,
        )
        return CouncilCycleDetail(
            schema_version="council-cycle.v1",
            cycle_id=packet.cycle_id,
            evidence_hash=packet.evidence_hash,
            status=result.status,
            phase="commit",
            started_at=now,
            finished_at=datetime.now(UTC),
            deadline_s=elapsed_s,
            claims=[],
            challenges=[],
            rejections=[],
            calls=[],
            result=result,
        )
