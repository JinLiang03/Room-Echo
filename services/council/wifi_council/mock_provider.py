"""Deterministic Council provider for replay, CI, and policy tests."""

from __future__ import annotations

import copy
from datetime import UTC, datetime
from typing import Any, Literal, TypeVar

from wifi_contracts import (
    AgentChallenge,
    AgentClaim,
    AgentRole,
    EvidencePacket,
    ProviderHealth,
)

from .config import CouncilConfig
from .grounding import (
    THEMED_ROLES,
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

T = TypeVar("T")
Misbehavior = Literal["none", "bad_refs", "overreach", "fabricated_number", "old_hash"]


_ROLE_UNCERTAINTY: dict[str, str] = {
    "architecture": "动线和层级只是当前标定下的代理关系,不是空间尺寸",
    "biota": "环境痕迹不指向任何具体对象,单个周期也不能证明持续性",
    "feng_shui": "气与明堂只作文化叙事,不能当作环境测量",
    "psyche": "空间松紧只描述界面叙事,不代表真实心理状态",
    "soundscape": "节拍与远近只作声景隐喻,不代表真实声音",
}

_ROLE_DISPLAY_NAMES: dict[str, str] = {
    "architecture": "空间结构视角",
    "biota": "环境痕迹视角",
    "feng_shui": "流动隐喻视角",
    "psyche": "空间心理视角",
    "soundscape": "声景视角",
    "skeptic": "证据怀疑视角",
    "fusion": "综合视角",
}

_MOTION_DISPLAY = {
    "idle": "平稳",
    "micro_motion": "轻微变化",
    "moving": "持续变化",
    "fast_change": "快速变化",
    "unknown": "未知",
}
_OCCUPANCY_DISPLAY = {
    "low": "低",
    "medium": "中",
    "high": "高",
    "unknown": "未知",
}
_DEPTH_DISPLAY = {
    "near": "偏近",
    "mid": "居中",
    "far": "偏远",
    "unknown": "未知",
}


def _plain_role_reading(
    role: str,
    reaction: SpatialLifeReaction,
    primary: dict[str, Any],
) -> str:
    """Return one role-distinct Mock sentence for the audit record."""
    concept = str(primary.get("concept", "空间"))
    if role == "architecture":
        body = (
            f"空间的形:边界呈{reaction.occupancy},层次{reaction.depth},"
            f"动线随{reaction.motion}而变化"
        )
    elif role == "biota":
        body = (
            f"空间的息:活动呈{reaction.motion},环境痕迹{reaction.occupancy},"
            f"相对走向{reaction.depth}"
        )
    elif role == "feng_shui":
        body = (
            f"空间的流:借{concept}把{reaction.motion}读成流速、"
            f"把{reaction.occupancy}读成聚散、把{reaction.depth}读成远近"
        )
    elif role == "psyche":
        body = (
            f"空间的势:活动呈{reaction.motion}、边界{reaction.occupancy}、"
            f"层次{reaction.depth};只描述房间气质"
        )
    elif role == "soundscape":
        body = (
            f"共识运动映射:{reaction.motion}对应节奏与音高、"
            f"{reaction.occupancy}对应厚薄、{reaction.depth}对应远近"
        )
    else:
        body = f"以{concept}解释当前三个代理的变化"
    return f"{body}(叙事隐喻)"



class MockAgentProvider:
    """Deterministic themed council; fixed seed + template version.

    Five interpretation lenses (architecture/biota/feng_shui/psyche/
    soundscape) propose metaphor readings grounded in curated knowledge
    bases (data/knowledge/*.json); the skeptic cross-examines every claim
    with falsificationist challenges. Fusion assembles deterministically.
    """

    name = "mock"

    def __init__(
        self,
        config: CouncilConfig,
        *,
        misbehave: Misbehavior = "none",
        misbehave_role: AgentRole = "feng_shui",
        demo_scenario: bool = False,
    ) -> None:
        self.config = config
        self.model = "mock"
        self.misbehave = misbehave
        self.misbehave_role = misbehave_role
        self.demo_scenario = demo_scenario
        self.template_version = config.mock_template_version
        self._cache: dict[tuple[str, ...], ProviderCall[Any]] = {}

    def _cached(
        self,
        key: tuple[str, ...],
        value: T | None,
        *,
        input_tokens: int = 0,
        output_tokens: int = 0,
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
            latency_ms=1,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        )
        self._cache[key] = call
        return call

    def health(self) -> ProviderHealth:
        return ProviderHealth(
            schema_version="provider-health.v1",
            provider="mock",
            status="ok",
            model=self.model,
            detail="deterministic themed mock council",
            checked_at=datetime.now(UTC),
        )

    # ---- propose --------------------------------------------------------

    async def propose(
        self,
        role: AgentRole,
        packet: EvidencePacket,
        prompt: PromptVersion,
    ) -> ProviderCall[SpecialistProposal]:
        if role not in THEMED_ROLES:
            raise ValueError(f"mock provider cannot propose for role {role!r}")
        key = (
            self.name,
            role,
            "propose",
            prompt.version,
            prompt.sha256,
            packet.evidence_hash,
            self.misbehave,
        )
        proposal = self._propose_themed(packet, role)
        if (
            self.demo_scenario
            and role == "feng_shui"
            and packet.cycle_id == "cycle-0003"
        ):
            # Demo-only controlled overreach so the PolicyArbiter rejection
            # path is visible in the two-minute demo.
            proposal = proposal.model_copy(
                update={"plain_language": "此方位距离 3.2 米,大吉(叙事隐喻)"}
            )
        if self.misbehave_role == role:
            proposal = self._apply_misbehavior(packet, proposal)
        proposal.validate_for(packet, role)
        return self._cached(key, proposal)

    def _propose_themed(
        self,
        packet: EvidencePacket,
        role: AgentRole,
    ) -> SpecialistProposal:
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
                plain_language=(
                    f"{_ROLE_DISPLAY_NAMES[role]}:当前必需代理含 unknown,"
                    "不能回答 J 的空间节奏问题"
                ),
                uncertainty="证据不足,只能保持未知",
                evidence_refs=refs,
                falsification_test="等待三个代理与质量均恢复可用后再评估",
                reasoning_summary="当前快照未满足同场景问题的最小证据条件",
            )
        knowledge = load_role_knowledge(role)
        entries = knowledge.get("entries", [])
        if not entries:
            raise ValueError(f"knowledge base empty for {role}")
        index = stable_index(packet, role)
        primary = entries[index % len(entries)]
        other = entries[(index + 1) % len(entries)]
        plain_language = _plain_role_reading(
            role,
            reaction,
            primary,
        )
        if "rx-a" in packet.window_summary.links:
            refs.append(evidence_ref(packet, "features/rx-a/temporal_diff_rms"))
        sources = [str(entry.get("url", "")) for entry in (primary, other)]
        steps = build_analysis_steps(
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
        proposal = SpecialistProposal(
            scene_question=PERSONAL_SCENE_QUESTION,
            measurement_summary=measurement,
            reaction=reaction,
            lens_focus=ROLE_LENS_FOCUS[role],
            scene_decision=decision,
            kind="observation",
            stance="supports",
            plain_language=plain_language,
            uncertainty=_ROLE_UNCERTAINTY[role],
            evidence_refs=refs,
            sources=[url for url in sources if url],
            process=(
                "同一问题:是否保存 J 的当前空间节奏;数据路径:"
                "motion|occupancy|depth|quality -> 角色知识映射 -> 受限叙事"
            ),
            analysis_steps=steps,
            systematic_reading=systematic,
            assumptions=["标定 profile 与当前拓扑匹配", "隐喻解读不等于测量"],
            alternative_explanations=[
                f"另一视角:{other['concept']}",
                "无线干扰或静态布置变化也可能形成相似代理组合",
            ],
            falsification_test=(
                "保持标定不变并对照下一周期;若三代理组合不延续,则撤回本解读"
            ),
            reasoning_summary=(
                f"quality={measurement.quality};按[{primary['concept']}]解释同一当前快照"
            ),
        )
        assert proposal.systematic_reading is not None
        return proposal.model_copy(
            update={
                "systematic_reading": proposal.systematic_reading.model_copy(
                    update={"headline": proposal.render_proposition()}
                )
            }
        )

    def _apply_misbehavior(
        self,
        packet: EvidencePacket,
        proposal: SpecialistProposal,
    ) -> SpecialistProposal:
        if self.misbehave == "none":
            return proposal
        if self.misbehave == "bad_refs":
            return proposal.model_copy(
                update={
                    "evidence_refs": [
                        f"evidence://{packet.evidence_hash}/signals/motion/nonexistent"
                    ]
                }
            )
        if self.misbehave == "old_hash":
            return proposal.model_copy(
                update={
                    "evidence_refs": [
                        f"evidence://sha256:{'1' * 64}/signals/motion/value"
                    ]
                }
            )
        if self.misbehave == "overreach":
            return proposal.model_copy(
                update={"plain_language": "墙后有人,能看出一个人"}
            )
        if self.misbehave == "fabricated_number":
            return proposal.model_copy(
                update={"plain_language": "检测到运动,距离约 3.2 米"}
            )

    # ---- challenge / respond / synthesize ------------------------------

    async def challenge(
        self,
        packet: EvidencePacket,
        claims: list[AgentClaim],
        prompt: PromptVersion,
    ) -> ProviderCall[ChallengeSet]:
        key = (
            self.name,
            "skeptic",
            "cross_examine",
            prompt.version,
            prompt.sha256,
            packet.evidence_hash,
        )
        challenges: list[AgentChallengeOutput] = []
        non_abstain = [claim for claim in claims if claim.stance == "supports"]
        for claim in non_abstain:
            subject = self._skeptic_subject(packet, claim)
            if self._claim_contradicts_sensor(packet, claim):
                challenges.append(
                    AgentChallengeOutput(
                        target_claim_id=claim.claim_id,
                        category="stale_evidence",
                        proposed_severity="blocking",
                        statement=f"{subject}:必需代理含 unknown,当前解释不能成立",
                        evidence_refs=context_refs(packet),
                        resolution_test="等待三个代理与质量均可用的新周期后再检验该主张",
                    )
                )
            if not self._claim_is_labeled_metaphor(claim):
                challenges.append(
                    AgentChallengeOutput(
                        target_claim_id=claim.claim_id,
                        category="causal_overreach",
                        proposed_severity="blocking",
                        statement=f"{subject}:没有标明叙事隐喻,容易被误读为测量",
                        evidence_refs=context_refs(packet),
                        resolution_test="明确叙事边界后,用同一 EvidencePacket 重新生成该主张",
                    )
                )
        if "interference_high" in packet.quality.quality_flags and non_abstain:
            target = next(
                (
                    claim
                    for claim in non_abstain
                    if claim.role == "feng_shui"
                ),
                non_abstain[0],
            )
            challenges.append(
                AgentChallengeOutput(
                    target_claim_id=target.claim_id,
                    category="confound",
                    proposed_severity="material",
                    statement=(
                        f"{self._skeptic_subject(packet, target)}:干扰标记也可能造成"
                        "相似反应词,不能直接保存为稳定节奏"
                    ),
                    evidence_refs=context_refs(packet),
                    resolution_test="对照无干扰的新周期;若三代理组合不延续则撤回该主张",
                )
            )
        if self.demo_scenario and packet.cycle_id == "cycle-0004" and non_abstain:
            challenges.append(
                AgentChallengeOutput(
                    target_claim_id=non_abstain[0].claim_id,
                    category="causal_overreach",
                    proposed_severity="blocking",
                    statement=(
                        f"{self._skeptic_subject(packet, non_abstain[0])}:"
                        "演示注入的越界无法由当前快照解除"
                    ),
                    evidence_refs=context_refs(packet),
                    resolution_test="提供新的三代理与质量快照后再评估该主张",
                )
            )
        if not challenges and non_abstain:
            target = non_abstain[
                stable_index(packet, "skeptic", "target") % len(non_abstain)
            ]
            challenges.append(
                AgentChallengeOutput(
                    target_claim_id=target.claim_id,
                    category="confound",
                    proposed_severity="info",
                    statement=(
                        f"{self._skeptic_subject(packet, target)}:quality="
                        f"{packet.quality.overall_status} 只说明本周期可用,"
                        "静态布置变化仍可能形成相似代理组合"
                    ),
                    evidence_refs=context_refs(packet),
                    resolution_test="保持标定不变并对照下一周期;若组合不延续则撤回该主张",
                )
            )
        challenges = challenges[: self.config.max_challenges_total]
        return self._cached(key, ChallengeSet(challenges=challenges))

    @staticmethod
    def _claim_is_labeled_metaphor(claim: AgentClaim) -> bool:
        return "隐喻" in claim.proposition or "metaphor" in claim.proposition.lower()

    @staticmethod
    def _skeptic_subject(packet: EvidencePacket, claim: AgentClaim) -> str:
        return (
            f"针对「{_ROLE_DISPLAY_NAMES.get(claim.role, '当前角色')}」的本轮观点"
            f"(活动={_MOTION_DISPLAY[packet.signals.motion.state]}、"
            f"占用={_OCCUPANCY_DISPLAY[packet.signals.occupancy_density.state]}、"
            f"相对纵深={_DEPTH_DISPLAY[packet.signals.depth_zone.state]})"
        )

    def _claim_contradicts_sensor(
        self,
        packet: EvidencePacket,
        claim: AgentClaim,
    ) -> bool:
        refs = " ".join([*claim.evidence_refs, *claim.counter_evidence_refs])
        if "signals/motion" in refs and packet.signals.motion.state == "unknown":
            return True
        if (
            "signals/occupancy" in refs
            and packet.signals.occupancy_density.state == "unknown"
        ):
            return True
        return (
            "signals/depth" in refs
            and packet.signals.depth_zone.state == "unknown"
        )

    async def respond(
        self,
        packet: EvidencePacket,
        claim: AgentClaim,
        challenges: list[AgentChallenge],
        prompt: PromptVersion,
    ) -> ProviderCall[ResponseOutput]:
        key = (
            self.name,
            claim.role,
            "respond",
            prompt.version,
            prompt.sha256,
            packet.evidence_hash,
            claim.claim_id,
        )
        severities = [challenge.proposed_severity for challenge in challenges]
        if "blocking" in severities:
            return self._cached(
                key,
                ResponseOutput(
                    state="conceded",
                    reasoning_summary="存在 blocking 质疑;concede 该主张.",
                ),
            )
        if "material" in severities:
            return self._cached(
                key,
                ResponseOutput(
                    state="revised",
                    proposition=claim.proposition + "(在 material 质疑下仅作受限解读)",
                    alternative_explanations=list(claim.alternative_explanations),
                    falsification_test=claim.falsification_test,
                    reasoning_summary="保留隐喻但补充受限范围.",
                ),
            )
        return self._cached(
            key,
            ResponseOutput(
                state="revised",
                proposition=claim.proposition,
                falsification_test=claim.falsification_test,
                reasoning_summary="无 material/blocking 质疑;维持主张.",
            ),
        )

    async def synthesize(
        self,
        approved: ApprovedCouncilInput,
        prompt: PromptVersion,
    ) -> ProviderCall[SynthesisOutput]:
        key = (
            self.name,
            "fusion",
            "synthesize",
            prompt.version,
            prompt.sha256,
            approved.packet.evidence_hash,
        )
        packet = approved.packet
        measurement = ProxyMeasurementSummary.from_packet(packet)
        reaction = SpatialLifeReaction.from_measurement(measurement)
        if approved.status == "unavailable":
            headline = "我还没有成形"
            plain_language = "我还没有成形:当前快照不能形成可靠的空间节奏解释"
            action = "请先恢复标定和信号质量,再让我观察新周期"
            uncertainty = "当前只能保持未知"
        elif approved.status == "ambiguous":
            headline = "我仍在漂浮"
            plain_language = "我仍在漂浮:干扰或静态布置这一替代解释尚未排除"
            action = "请保持房间条件不变,让我再观察一个周期后再决定是否保存"
            uncertainty = "未解决质疑存在时只能作为候选,不能当作稳定结论"
        else:
            headline = "我正在回应这个房间"
            plain_language = (
                f"我正以{reaction.motion}的节奏、{reaction.occupancy}的边界和"
                f"{reaction.depth}的层次回应这个房间"
            )
            action = "如果这正是你想记住的时刻,请保存我并与下一周期对照"
            uncertainty = "只在当前 quality 与标定条件内成立"
        alternatives: list[str] = []
        limitations: list[str] = []
        for claim in approved.claims:
            alternatives.extend(claim.alternative_explanations)
            limitations.extend(claim.assumptions)
        limitations.append("隐喻解读不等于测量;非影像、非人数、非米制距离")
        if not packet.topology.depth_output_allowed:
            limitations.append("单 RX:depth 保持 unknown")
        return self._cached(
            key,
            SynthesisOutput(
                measurement_summary=measurement,
                reaction=reaction,
                headline=headline,
                plain_language=plain_language,
                action=action,
                uncertainty=uncertainty,
                alternatives=list(dict.fromkeys(alternatives)),
                limitations=list(dict.fromkeys(limitations)),
                visual_parameters={"palette": "proxy_blue", "shape": "rings"},
                audio_parameters={"enabled": "false", "tone": "neutral"},
            ),
        )


__all__ = ["Misbehavior", "MockAgentProvider"]
