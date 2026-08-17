"""Deterministic PolicyArbiter: schema, refs, numbers, forbidden claims,
topology/calibration gates, challenge severity, and confidence invariants.

The arbiter is a program, never an LLM. Every rejection carries a stable
reason code and is written to the audit log (AGENT_COUNCIL.md section 9).
"""

from __future__ import annotations

import re
from datetime import UTC, datetime
from typing import Any, Literal, cast

from pydantic import BaseModel, ConfigDict, Field
from wifi_contracts import (
    AgentChallenge,
    AgentClaim,
    AgentRole,
    EvidencePacket,
    PolicyRejection,
)

from .config import CouncilConfig
from .outputs import SynthesisOutput

REASON_INVALID_SCHEMA = "invalid_schema"
REASON_HASH_MISMATCH = "hash_mismatch"
REASON_UNKNOWN_REF = "unknown_evidence_ref"
REASON_NON_SCALAR_REF = "non_scalar_evidence_ref"
REASON_CYCLE_MISMATCH = "cycle_mismatch"
REASON_FABRICATED_NUMBER = "fabricated_number"
REASON_FORBIDDEN_PERSON_COUNT = "forbidden_person_count"
REASON_FORBIDDEN_IDENTITY = "forbidden_identity"
REASON_FORBIDDEN_POSE = "forbidden_pose"
REASON_FORBIDDEN_METRIC_DEPTH = "forbidden_metric_depth"
REASON_FORBIDDEN_HEALTH = "forbidden_health"
REASON_FORBIDDEN_WALL_PRESENCE = "forbidden_wall_presence"
REASON_FORBIDDEN_VISION_LANGUAGE = "forbidden_vision_language"
REASON_DEPTH_REQUIRED_UNKNOWN = "depth_required_unknown"
REASON_OCCUPANCY_DEPTH_UNAVAILABLE = "occupancy_or_depth_unavailable"
REASON_UNAVAILABLE_NARRATED = "unavailable_narrated_as_present"
REASON_UNKNOWN_TARGET = "unknown_target_claim"
REASON_UNKNOWN_MAPPING_KEY = "unknown_mapping_key"
REASON_CONFIDENCE_INVARIANT = "confidence_invariant"
REASON_UNLABELED_METAPHOR = "unlabeled_metaphor"

# (reason_code, regex). Negation lookbehinds keep "非人数"/"不是人数" safe.
_FORBIDDEN_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    (
        REASON_FORBIDDEN_PERSON_COUNT,
        re.compile(
            r"(?<!非)(?<!不是)(?<!或)(?<!和)(?<!与)(?<!之)人数|"
            r"两个人|三个人|几个人|一个人|发现.{0,6}人|"
            r"\bpeople\b|\bpersons?\b"
        ),
    ),
    (
        REASON_FORBIDDEN_IDENTITY,
        re.compile(r"身份|是谁|识别出谁|\bidentity\b|recogni[sz]e"),
    ),
    (REASON_FORBIDDEN_POSE, re.compile(r"姿态|姿势|手势|坐姿|站姿|\bpose\b|\bposture\b")),
    (
        REASON_FORBIDDEN_METRIC_DEPTH,
        re.compile(
            r"\d+(?:\.\d+)?\s*(?:米|meters?)\b|三维重建|深度图|metric depth"
        ),
    ),
    (
        REASON_FORBIDDEN_HEALTH,
        re.compile(r"心率|呼吸率|血压|健康风险|危险行为|heart rate|breathing rate"),
    ),
    (
        REASON_FORBIDDEN_WALL_PRESENCE,
        re.compile(r"墙后|穿墙|隔墙|透过墙|behind the wall|through[- ]wall"),
    ),
    (
        REASON_FORBIDDEN_VISION_LANGUAGE,
        re.compile(r"摄像头|相机图像|拍摄到|成像|看见|看到|visual image"),
    ),
    (
        REASON_FABRICATED_NUMBER,
        re.compile(r"\b(?:probability|confidence|score|probability)[:=]\s*\d"),
    ),
]

_SEVERITY_ORDER = {"info": 0, "material": 1, "blocking": 2}
_SEVERITY_FLOOR: dict[str, str] = {
    "confound": "material",
    "missing_evidence": "material",
    "calibration_mismatch": "blocking",
    "causal_overreach": "blocking",
    "contradiction": "material",
    "stale_evidence": "blocking",
}

_PRESENCE_WORDS = (
    "moving",
    "fast_change",
    "low",
    "medium",
    "high",
    "near",
    "mid",
    "far",
    "占用",
    "遮挡",
    "纵深",
    "动态",
    "运动",
)

_VISUAL_MAPPING_KEYS = {"palette", "shape", "intensity_level", "mode"}
_AUDIO_MAPPING_KEYS = {"enabled", "tone", "motion_scale", "mode"}
_AGENT_ROLE_VALUES = {
    "architecture",
    "biota",
    "feng_shui",
    "psyche",
    "soundscape",
    "skeptic",
    "fusion",
}


def _safe_role(role: str) -> AgentRole:
    """Never crash on a provider-supplied role string (hardening)."""
    return cast(AgentRole, role) if role in _AGENT_ROLE_VALUES else "skeptic"


class PolicyVerdict(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["supported", "ambiguous", "unavailable"]
    accepted_claims: list[AgentClaim] = Field(default_factory=list)
    rejected_claims: list[AgentClaim] = Field(default_factory=list)
    rejections: list[PolicyRejection] = Field(default_factory=list)
    challenges: list[AgentChallenge] = Field(default_factory=list)
    unresolved_challenges: list[AgentChallenge] = Field(default_factory=list)
    model_support: float = Field(ge=0, le=1)
    display_confidence: float = Field(ge=0, le=1)
    evidence_ceiling: float = Field(ge=0, le=1)
    limitations: list[str] = Field(default_factory=list)


class EvidenceResolver:
    """Resolves `evidence://{hash}/{path}` refs inside the current packet."""

    @staticmethod
    def resolve(
        packet: EvidencePacket,
        ref: str,
    ) -> tuple[Literal["ok", "hash_mismatch", "unknown_ref", "non_scalar"], Any]:
        if not ref.startswith("evidence://"):
            return "unknown_ref", None
        rest = ref[len("evidence://") :]
        if "/" not in rest:
            return "unknown_ref", None
        ref_hash, path = rest.split("/", 1)
        if ref_hash != packet.evidence_hash:
            return "hash_mismatch", None
        if not path:
            return "unknown_ref", None
        if path in packet.evidence_index:
            value: Any = packet.evidence_index[path].value
        else:
            value = EvidenceResolver._walk(packet.model_dump(mode="json"), path)
            if value is _MISSING:
                return "unknown_ref", None
        if not isinstance(value, (str, int, float, bool)):
            return "non_scalar", value
        return "ok", value

    @staticmethod
    def _walk(node: Any, path: str) -> Any:
        tokens = path.split("/")
        if tokens[0] == "features":
            links = node.get("window_summary", {}).get("links", {})
            if len(tokens) < 3 or tokens[1] not in links:
                return _MISSING
            node = links[tokens[1]]
            tokens = tokens[2:]
        for token in tokens:
            if isinstance(node, dict) and token in node:
                node = node[token]
            elif isinstance(node, list) and token.isdigit() and int(token) < len(node):
                node = node[int(token)]
            else:
                return _MISSING
        return node


class _Missing:
    pass


_MISSING = _Missing()


class PolicyArbiter:
    """Deterministic validation; confidence never comes from agents."""

    def __init__(self, config: CouncilConfig) -> None:
        self.config = config

    def scan_text(self, text: str) -> list[tuple[str, str]]:
        problems: list[tuple[str, str]] = []
        for code, pattern in _FORBIDDEN_PATTERNS:
            match = pattern.search(text)
            if match:
                problems.append((code, f"匹配文本:{match.group(0)!r}"))
        return problems

    # ---- claims ---------------------------------------------------------

    def _claim_problems(
        self,
        packet: EvidencePacket,
        claim: AgentClaim,
    ) -> list[tuple[str, str]]:
        problems: list[tuple[str, str]] = []
        if claim.cycle_id != packet.cycle_id:
            problems.append((REASON_CYCLE_MISMATCH, "claim.cycle_id != packet.cycle_id"))
        for ref in [*claim.evidence_refs, *claim.counter_evidence_refs]:
            ref_status, _value = EvidenceResolver.resolve(packet, ref)
            if ref_status == "hash_mismatch":
                problems.append((REASON_HASH_MISMATCH, f"ref 使用旧/其他 hash:{ref}"))
            elif ref_status == "unknown_ref":
                problems.append((REASON_UNKNOWN_REF, f"ref 不存在于当前包:{ref}"))
            elif ref_status == "non_scalar":
                problems.append((REASON_NON_SCALAR_REF, f"ref 不是标量:{ref}"))
        text_fields = [
            claim.proposition,
            claim.falsification_test,
            claim.reasoning_summary,
            *claim.assumptions,
            *claim.alternative_explanations,
        ]
        reading = claim.systematic_reading
        if reading is not None:
            text_fields.extend(
                [
                    reading.headline,
                    reading.scene_sketch,
                    reading.narrative,
                    *reading.boundary_notes,
                    *reading.multimodal_hints,
                    *[layer.metaphor for layer in reading.layers],
                    *[layer.explanation for layer in reading.layers],
                ]
            )
        for text in text_fields:
            problems.extend(self.scan_text(text))
        refs = " ".join([*claim.evidence_refs, *claim.counter_evidence_refs])
        if (
            "signals/depth" in refs
            and claim.stance == "supports"
            and not packet.topology.depth_output_allowed
        ):
            problems.append(
                (REASON_DEPTH_REQUIRED_UNKNOWN, "单 RX 时 depth 必须 unknown")
            )
        status = packet.signals.status
        if (
            ("signals/occupancy" in refs or "signals/depth" in refs)
            and claim.stance == "supports"
            and (status == "uncalibrated" or packet.quality.overall_status == "uncalibrated")
        ):
            problems.append(
                (
                    REASON_OCCUPANCY_DEPTH_UNAVAILABLE,
                    "标定/topology 失配时 occupancy/depth 不可用",
                )
            )
        if status in ("insufficient_signal", "uncalibrated") and claim.stance == "supports":
            problems.append(
                (
                    REASON_UNAVAILABLE_NARRATED,
                    "信号 unavailable 时不能以 present 叙述",
                )
            )
        if (
            claim.lens == "metaphor"
            and claim.kind != "limitation"
            and "隐喻" not in claim.proposition
            and "metaphor" not in claim.proposition.lower()
        ):
            problems.append(
                (
                    REASON_UNLABELED_METAPHOR,
                    "隐喻解读必须标注“(隐喻解读)”以与测量区分",
                )
            )
        return problems

    # ---- challenges -----------------------------------------------------

    def _challenge_problems(
        self,
        packet: EvidencePacket,
        challenge: AgentChallenge,
        claim_ids: set[str],
    ) -> list[tuple[str, str]]:
        problems: list[tuple[str, str]] = []
        if challenge.target_claim_id not in claim_ids:
            problems.append((REASON_UNKNOWN_TARGET, "target claim 不在本周期"))
        for ref in challenge.evidence_refs:
            status, _value = EvidenceResolver.resolve(packet, ref)
            if status == "hash_mismatch":
                problems.append((REASON_HASH_MISMATCH, f"ref 使用旧/其他 hash:{ref}"))
            elif status == "unknown_ref":
                problems.append((REASON_UNKNOWN_REF, f"ref 不存在于当前包:{ref}"))
            elif status == "non_scalar":
                problems.append((REASON_NON_SCALAR_REF, f"ref 不是标量:{ref}"))
        for text in (challenge.statement, challenge.resolution_test):
            problems.extend(self.scan_text(text))
        return problems

    def confirm_severity(self, challenge: AgentChallenge) -> AgentChallenge:
        floor = _SEVERITY_FLOOR[challenge.category]
        final = (
            floor
            if _SEVERITY_ORDER[floor] >= _SEVERITY_ORDER[challenge.proposed_severity]
            else challenge.proposed_severity
        )
        if final != challenge.proposed_severity:
            return challenge.model_copy(update={"proposed_severity": final})
        return challenge

    # ---- confidence chain ----------------------------------------------

    def _confidences(
        self,
        packet: EvidencePacket,
        unresolved: list[AgentChallenge],
    ) -> tuple[float, float, Literal["supported", "ambiguous", "unavailable"], float]:
        signals = packet.signals
        cap = signals.sensor_confidence_cap
        model_support = min(
            signals.motion.confidence,
            signals.occupancy_density.confidence,
            signals.depth_zone.confidence,
        )
        if signals.status in ("insufficient_signal", "uncalibrated"):
            model_support = 0.0
        topology_cap = 1.0 if packet.topology.depth_output_allowed else 0.0
        ceiling = min(cap, topology_cap)
        model_support = min(model_support, ceiling)

        if model_support <= 0.0 or signals.status in (
            "insufficient_signal",
            "uncalibrated",
        ):
            return ceiling, ceiling, "unavailable", 0.0
        severities = {challenge.proposed_severity for challenge in unresolved}
        if "blocking" in severities:
            display = model_support * self.config.blocking_penalty
            return ceiling, model_support, "ambiguous", round(display, 6)
        if "material" in severities:
            display = model_support * self.config.material_penalty
            return ceiling, model_support, "ambiguous", round(display, 6)
        return ceiling, model_support, "supported", round(model_support, 6)

    # ---- main entry -----------------------------------------------------

    def arbitrate(
        self,
        packet: EvidencePacket,
        claims: list[AgentClaim],
        challenges: list[AgentChallenge],
        *,
        now: datetime | None = None,
    ) -> PolicyVerdict:
        now = now or datetime.now(UTC)
        claim_ids = {claim.claim_id for claim in claims}
        accepted: list[AgentClaim] = []
        rejected: list[AgentClaim] = []
        rejections: list[PolicyRejection] = []

        for claim in claims:
            problems = self._claim_problems(packet, claim)
            if problems:
                rejected.append(claim)
                for code, detail in problems:
                    rejections.append(
                        PolicyRejection(
                            schema_version="policy-rejection.v1",
                            rejection_id=f"rejection-{packet.cycle_id}-{len(rejections) + 1:04d}",
                            cycle_id=packet.cycle_id,
                            target_id=claim.claim_id,
                            agent_id=claim.agent_id,
                            role=_safe_role(claim.role),
                            reason_code=code,
                            detail=detail,
                            rejected_at=now,
                        )
                    )
            else:
                accepted.append(claim.model_copy(update={"state": "accepted"}))

        adjusted: list[AgentChallenge] = []
        unresolved: list[AgentChallenge] = []
        for challenge in challenges:
            problems = self._challenge_problems(packet, challenge, claim_ids)
            if problems:
                rejected_challenge = challenge.model_copy(
                    update={"status": "rejected_by_policy"}
                )
                adjusted.append(rejected_challenge)
                for code, detail in problems:
                    rejections.append(
                        PolicyRejection(
                            schema_version="policy-rejection.v1",
                            rejection_id=f"rejection-{packet.cycle_id}-{len(rejections) + 1:04d}",
                            cycle_id=packet.cycle_id,
                            target_id=challenge.challenge_id,
                            agent_id=challenge.challenger_agent_id,
                            role="skeptic",
                            reason_code=code,
                            detail=detail,
                            rejected_at=now,
                        )
                    )
            else:
                confirmed = self.confirm_severity(challenge)
                adjusted.append(confirmed)
                if confirmed.status == "open":
                    unresolved.append(confirmed)

        ceiling, model_support, status, display = self._confidences(packet, unresolved)
        if display > model_support or model_support > ceiling:
            rejections.append(
                PolicyRejection(
                    schema_version="policy-rejection.v1",
                    rejection_id=f"rejection-{packet.cycle_id}-{len(rejections) + 1:04d}",
                    cycle_id=packet.cycle_id,
                    target_id=packet.cycle_id,
                    agent_id="policy",
                    role="fusion",
                    reason_code=REASON_CONFIDENCE_INVARIANT,
                    detail="display_confidence <= model_support <= evidence_ceiling violated",
                    rejected_at=now,
                )
            )
            display = 0.0
            model_support = 0.0
            status = "unavailable"

        limitations: list[str] = []
        if not packet.topology.depth_output_allowed:
            limitations.append("单 RX:depth 保持 unknown")
        if packet.signals.status == "uncalibrated":
            limitations.append("标定/topology 失配:occupancy/depth unavailable")
        if any(challenge.proposed_severity in ("material", "blocking") for challenge in unresolved):
            limitations.append("存在未解决 material/blocking 挑战")
        if not limitations:
            limitations.append("代理信号,非影像、非人数、非米制距离")

        return PolicyVerdict(
            status=status,
            accepted_claims=accepted,
            rejected_claims=rejected,
            rejections=rejections,
            challenges=adjusted,
            unresolved_challenges=unresolved,
            model_support=round(model_support, 6),
            display_confidence=round(display, 6),
            evidence_ceiling=round(ceiling, 6),
            limitations=limitations,
        )

    # ---- fusion synthesis validation -----------------------------------

    def validate_synthesis(
        self,
        packet: EvidencePacket,
        synthesis: SynthesisOutput,
        verdict: PolicyVerdict,
        *,
        now: datetime | None = None,
    ) -> list[PolicyRejection]:
        now = now or datetime.now(UTC)
        rejections: list[PolicyRejection] = []

        def add(target_id: str, agent_id: str, role: AgentRole, code: str, detail: str) -> None:
            rejections.append(
                PolicyRejection(
                    schema_version="policy-rejection.v1",
                    rejection_id=f"rejection-{packet.cycle_id}-{len(rejections) + 1:04d}",
                    cycle_id=packet.cycle_id,
                    target_id=target_id,
                    agent_id=agent_id,
                    role=role,
                    reason_code=code,
                    detail=detail,
                    rejected_at=now,
                )
            )

        for text in (
            synthesis.headline,
            synthesis.plain_language,
            synthesis.action,
            synthesis.uncertainty,
            *synthesis.alternatives,
            *synthesis.limitations,
        ):
            for code, detail in self.scan_text(text):
                add("fusion", "agent-fusion", "fusion", code, detail)
        if verdict.status == "unavailable" and any(
            word in synthesis.plain_language
            or word in synthesis.action
            or word in synthesis.headline
            for word in _PRESENCE_WORDS
        ):
            add(
                "fusion",
                "agent-fusion",
                "fusion",
                REASON_UNAVAILABLE_NARRATED,
                "unavailable 状态不能被叙述为存在",
            )
        for key in synthesis.visual_parameters:
            if key not in _VISUAL_MAPPING_KEYS:
                add("fusion", "agent-fusion", "fusion", REASON_UNKNOWN_MAPPING_KEY, f"visual key {key}")
        for key in synthesis.audio_parameters:
            if key not in _AUDIO_MAPPING_KEYS:
                add("fusion", "agent-fusion", "fusion", REASON_UNKNOWN_MAPPING_KEY, f"audio key {key}")
        return rejections
