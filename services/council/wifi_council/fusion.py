"""Deterministic Fusion assembler: copies approved numbers verbatim.

The assembler is the safe default. A provider synthesis is used only after
the PolicyArbiter validates it; otherwise the deterministic narrative wins so
the UI never receives unvalidated LLM prose (AGENT_COUNCIL.md section 8).
"""

from __future__ import annotations

from datetime import datetime

from wifi_contracts import (
    AgreementSummary,
    CouncilResult,
    EvidencePacket,
    Provenance,
)

from .actions import build_agent_action_decision
from .config import CouncilConfig
from .outputs import (
    ApprovedCouncilInput,
    ProxyMeasurementSummary,
    SpatialLifeReaction,
    SynthesisOutput,
)
from .policy import PolicyVerdict
from .presentation import (
    build_sound_consensus_motion,
    build_spatial_life_interaction,
)

DEFAULT_VISUAL = {"palette": "proxy_blue", "shape": "rings"}
DEFAULT_AUDIO = {"enabled": "false", "tone": "neutral"}


class FusionAssembler:
    def __init__(self, config: CouncilConfig) -> None:
        self.config = config

    def _approved(
        self,
        packet: EvidencePacket,
        verdict: PolicyVerdict,
    ) -> ApprovedCouncilInput:
        return ApprovedCouncilInput(
            packet=packet,
            claims=verdict.accepted_claims,
            challenges=verdict.unresolved_challenges,
            status=verdict.status,
            sensor_confidence_cap=packet.signals.sensor_confidence_cap,
            model_support=verdict.model_support,
            display_confidence=verdict.display_confidence,
        )

    def _fallback_narrative(
        self,
        packet: EvidencePacket,
        verdict: PolicyVerdict,
    ) -> SynthesisOutput:
        measurement = ProxyMeasurementSummary.from_packet(packet)
        reaction = SpatialLifeReaction.from_measurement(measurement)
        if verdict.status == "unavailable":
            return SynthesisOutput(
                measurement_summary=measurement,
                reaction=reaction,
                headline="我还没有成形",
                plain_language="我还没有成形:当前快照不能形成可靠的空间节奏解释",
                action="请先恢复标定和信号质量,再让我观察新周期",
                uncertainty="当前只能保持未知",
                limitations=["代理信号,非影像、非人数、非米制距离"],
                visual_parameters=dict(DEFAULT_VISUAL),
                audio_parameters=dict(DEFAULT_AUDIO),
            )
        if verdict.status == "ambiguous":
            return SynthesisOutput(
                measurement_summary=measurement,
                reaction=reaction,
                headline="我仍在漂浮",
                plain_language="我仍在漂浮:怀疑者尚未排除当前快照的替代解释",
                action="请先按质疑项完成一次对照,再决定是否保存我",
                uncertainty="未解决质疑存在时只能作为候选",
                alternatives=[
                    claim.alternative_explanations[0]
                    for claim in verdict.accepted_claims
                    if claim.alternative_explanations
                ],
                limitations=verdict.limitations,
                visual_parameters=dict(DEFAULT_VISUAL),
                audio_parameters=dict(DEFAULT_AUDIO),
            )
        return SynthesisOutput(
            measurement_summary=measurement,
            reaction=reaction,
            headline="我正在回应这个房间",
            plain_language=(
                f"我正以{reaction.motion}的节奏、{reaction.occupancy}的边界和"
                f"{reaction.depth}的层次回应这个房间"
            ),
            action="如果这正是你想记住的时刻,请保存我并与下一周期对照",
            uncertainty="只在当前质量与标定条件内成立",
            alternatives=[
                alternative
                for claim in verdict.accepted_claims
                for alternative in claim.alternative_explanations
            ],
            limitations=verdict.limitations,
            visual_parameters=dict(DEFAULT_VISUAL),
            audio_parameters=dict(DEFAULT_AUDIO),
        )

    def assemble(
        self,
        packet: EvidencePacket,
        verdict: PolicyVerdict,
        *,
        synthesis: SynthesisOutput | None,
        features_version: str,
        prompt_version: str,
        provider_models: dict[str, str],
        generated_at: datetime,
    ) -> CouncilResult:
        narrative = synthesis or self._fallback_narrative(packet, verdict)
        narrative.validate_for(packet)
        participants = len(verdict.accepted_claims) + len(verdict.rejected_claims)
        supporting = sum(
            1 for claim in verdict.accepted_claims if claim.stance == "supports"
        )
        contradicting = sum(
            1 for claim in verdict.accepted_claims if claim.stance == "contradicts"
        )
        unresolved_ids = [
            challenge.challenge_id
            for challenge in verdict.unresolved_challenges
        ]
        agreement = AgreementSummary(
            participants=participants,
            supporting=supporting,
            contradicting=contradicting,
            unresolved_challenges=len(unresolved_ids),
            agreement_ratio=round(supporting / participants, 6) if participants else 0.0,
        )
        role_versions = {
            claim.role: claim.agent_version for claim in verdict.accepted_claims
        }
        return CouncilResult(
            schema_version="council-result.v1",
            cycle_id=packet.cycle_id,
            evidence_hash=packet.evidence_hash,
            status=verdict.status,
            headline=narrative.headline,
            summary=narrative.render_summary(),
            accepted_claim_ids=[
                claim.claim_id for claim in verdict.accepted_claims
            ],
            unresolved_challenge_ids=unresolved_ids,
            alternatives=list(dict.fromkeys(narrative.alternatives)),
            limitations=list(dict.fromkeys(narrative.limitations)),
            sensor_confidence_cap=packet.signals.sensor_confidence_cap,
            model_support=verdict.model_support,
            display_confidence=verdict.display_confidence,
            interpretation_agreement=agreement,
            visual_parameters=dict(narrative.visual_parameters),
            audio_parameters=dict(narrative.audio_parameters),
            sound_motion=build_sound_consensus_motion(
                packet,
                agreement,
                status=verdict.status,
            ),
            life_interaction=build_spatial_life_interaction(
                packet,
                status=verdict.status,
                provider_message=narrative.plain_language,
                provider_action=narrative.action,
            ),
            action_decision=build_agent_action_decision(
                packet,
                status=verdict.status,
                decision_confidence=verdict.display_confidence,
                decided_at=generated_at,
            ),
            provenance=Provenance(
                contracts_version="1.0.0",
                features_version=features_version,
                calibration_profile_id=packet.calibration.calibration_profile_id,
                agent_versions=role_versions,
                models=dict(provider_models),
                policy_version=self.config.policy_version,
                generated_at=generated_at,
            ),
        )
