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

from .config import CouncilConfig
from .outputs import ApprovedCouncilInput, SynthesisOutput
from .policy import PolicyVerdict

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

    def _fallback_narrative(self, verdict: PolicyVerdict) -> SynthesisOutput:
        if verdict.status == "unavailable":
            return SynthesisOutput(
                headline="信号不可用,讨论受限",
                summary="传感器信号 unavailable;不提供 presence 解读. ",
                limitations=["代理信号,非影像、非人数、非米制距离"],
                visual_parameters=dict(DEFAULT_VISUAL),
                audio_parameters=dict(DEFAULT_AUDIO),
            )
        if verdict.status == "ambiguous":
            unresolved = ", ".join(
                challenge.challenge_id
                for challenge in verdict.unresolved_challenges[:5]
            )
            return SynthesisOutput(
                headline="证据解读存在未解决质疑",
                summary=f"存在未解决挑战:{unresolved}. ",
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
            headline="代理信号的受限解读",
            summary=" ".join(
                claim.proposition for claim in verdict.accepted_claims[:3]
            )
            or "无 accepted 主张. ",
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
        narrative = synthesis or self._fallback_narrative(verdict)
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
            summary=narrative.summary,
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
