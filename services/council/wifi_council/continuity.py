"""Cross-cycle continuity for the seven visible Council roles.

This module is deliberately deterministic.  It compares only sealed proxy
states and links the current role record to the last committed role record.
The resulting context can shape Agent wording and UI effects, but it cannot
write to ``SignalTriplet`` or participate in confidence calculations.
"""

from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass
from typing import Literal, cast

from wifi_contracts import (
    AgentChallenge,
    AgentClaim,
    AgentContinuity,
    AgentRole,
    CouncilResult,
    EvidencePacket,
)

_MOTION_ORDER = {"idle": 0, "micro_motion": 1, "moving": 2, "fast_change": 3}
_OCCUPANCY_ORDER = {"low": 0, "medium": 1, "high": 2}
_DEPTH_ORDER = {"far": 0, "mid": 1, "near": 2}
_UNAVAILABLE_QUALITY = {"insufficient_signal", "uncalibrated"}
_MOTION_DELTA = 0.06
_DISTRIBUTION_DELTA = 0.10
_CONFIDENCE_DELTA = 0.08

ChangedSignal = Literal["motion", "occupancy", "depth", "quality"]
ContinuityRelation = Literal[
    "initial",
    "steady",
    "intensified",
    "eased",
    "shifted",
    "quality_changed",
    "recovered",
    "unknown",
]
_COMPARISON_SIGNALS: tuple[ChangedSignal, ...] = (
    "motion",
    "occupancy",
    "depth",
    "quality",
)

_STATE_LABELS = {
    "idle": "平稳",
    "micro_motion": "轻微变化",
    "moving": "持续变化",
    "fast_change": "快速变化",
    "low": "低",
    "medium": "中",
    "high": "高",
    "near": "偏近",
    "mid": "居中",
    "far": "偏远",
    "ok": "可用",
    "degraded": "降级",
    "insufficient_signal": "证据不足",
    "uncalibrated": "未标定",
    "unknown": "未知",
}


@dataclass(frozen=True)
class _RoleRecord:
    record_id: str
    text: str


@dataclass(frozen=True)
class _CycleSnapshot:
    packet: EvidencePacket
    records: dict[AgentRole, _RoleRecord]


@dataclass(frozen=True)
class ContinuityContext:
    """Provider-facing context plus the public deterministic record."""

    record: AgentContinuity
    previous_text: str | None

    def prompt_appendix(self) -> str:
        if self.record.relation == "initial":
            return (
                "跨周期上下文:这是本会话该角色的首次可审计观点。"
                "只解释当前 EvidencePacket。"
            )
        previous = (self.previous_text or "上一角色记录不可用").strip()[:320]
        return (
            "跨周期上下文(由确定性运行时生成,不得改写其中的状态):"
            f" relation={self.record.relation};"
            f" changed={','.join(self.record.changed_signals) or 'none'};"
            f" summary={self.record.summary};"
            f" previous_role_view={previous}. "
            "本轮回答须明确承接、修正或保持上一观点,同时只引用当前封存证据;"
            "上一观点不是新的传感器证据。"
        )


class CouncilContinuityTracker:
    """Keep one previous snapshot per session and bound total session memory."""

    def __init__(self, *, max_sessions: int = 32) -> None:
        if max_sessions < 1:
            raise ValueError("max_sessions must be positive")
        self.max_sessions = max_sessions
        self._previous: OrderedDict[str, _CycleSnapshot] = OrderedDict()

    def reset(self, session_id: str | None = None) -> None:
        if session_id is None:
            self._previous.clear()
        else:
            self._previous.pop(session_id, None)

    def context(self, packet: EvidencePacket, role: AgentRole) -> ContinuityContext:
        previous = self._previous.get(packet.session_id)
        if previous is None or packet.sequence <= previous.packet.sequence:
            return ContinuityContext(
                record=AgentContinuity(
                    relation="initial",
                    summary="首次封存:从当前活动、占用、相对纵深和质量开始建立角色观点。",
                ),
                previous_text=None,
            )
        self._previous.move_to_end(packet.session_id)

        role_record = previous.records.get(role)
        changed = _changed_signals(previous.packet, packet)
        relation = _relation(previous.packet, packet, changed)
        summary = _comparison_summary(previous.packet, packet, relation, changed)
        return ContinuityContext(
            record=AgentContinuity(
                previous_cycle_id=previous.packet.cycle_id,
                previous_record_id=(role_record.record_id if role_record is not None else None),
                previous_evidence_hash=previous.packet.evidence_hash,
                relation=relation,
                changed_signals=changed,
                summary=summary,
            ),
            previous_text=role_record.text if role_record is not None else None,
        )

    def commit(
        self,
        packet: EvidencePacket,
        claims: list[AgentClaim],
        challenges: list[AgentChallenge],
        result: CouncilResult | None,
    ) -> None:
        records: dict[AgentRole, _RoleRecord] = {}
        for claim in claims:
            if claim.role in {
                "architecture",
                "biota",
                "feng_shui",
                "psyche",
                "soundscape",
            }:
                role = cast(AgentRole, claim.role)
                records[role] = _RoleRecord(claim.claim_id, claim.proposition)
        safe_challenges = [
            item for item in challenges if item.status != "rejected_by_policy"
        ]
        challenge = next(
            (item for item in safe_challenges if item.status == "open"),
            safe_challenges[-1] if safe_challenges else None,
        )
        if challenge is not None:
            records["skeptic"] = _RoleRecord(
                challenge.challenge_id,
                challenge.statement,
            )
        if result is not None:
            records["fusion"] = _RoleRecord(result.cycle_id, result.summary)
        self._previous.pop(packet.session_id, None)
        self._previous[packet.session_id] = _CycleSnapshot(
            packet=packet.model_copy(deep=True),
            records=records,
        )
        while len(self._previous) > self.max_sessions:
            self._previous.popitem(last=False)


def _states(packet: EvidencePacket) -> dict[ChangedSignal, str]:
    return {
        "motion": packet.signals.motion.state,
        "occupancy": packet.signals.occupancy_density.state,
        "depth": packet.signals.depth_zone.state,
        "quality": packet.quality.overall_status,
    }


def _changed_signals(
    previous: EvidencePacket,
    current: EvidencePacket,
) -> list[ChangedSignal]:
    before = _states(previous)
    after = _states(current)
    deltas = _numeric_deltas(previous, current)
    thresholds: dict[ChangedSignal, float] = {
        "motion": _MOTION_DELTA,
        "occupancy": _DISTRIBUTION_DELTA,
        "depth": _DISTRIBUTION_DELTA,
        "quality": _CONFIDENCE_DELTA,
    }
    return [
        name
        for name in _COMPARISON_SIGNALS
        if before[name] != after[name] or abs(deltas[name]) >= thresholds[name]
    ]


def _numeric_deltas(
    previous: EvidencePacket,
    current: EvidencePacket,
) -> dict[ChangedSignal, float]:
    return {
        "motion": current.signals.motion.value - previous.signals.motion.value,
        "occupancy": _occupancy_level(current) - _occupancy_level(previous),
        "depth": _depth_level(current) - _depth_level(previous),
        "quality": (
            current.signals.sensor_confidence_cap
            - previous.signals.sensor_confidence_cap
        ),
    }


def _occupancy_level(packet: EvidencePacket) -> float:
    probabilities = packet.signals.occupancy_density.probabilities
    return probabilities.medium * 0.5 + probabilities.high


def _depth_level(packet: EvidencePacket) -> float:
    probabilities = packet.signals.depth_zone.probabilities
    return probabilities.mid * 0.5 + probabilities.near


def _relation(
    previous: EvidencePacket,
    current: EvidencePacket,
    changed: list[ChangedSignal],
) -> ContinuityRelation:
    before = _states(previous)
    after = _states(current)
    if after["quality"] in _UNAVAILABLE_QUALITY or "unknown" in after.values():
        return "unknown"
    if before["quality"] in _UNAVAILABLE_QUALITY and after["quality"] not in _UNAVAILABLE_QUALITY:
        return "recovered"
    if "quality" in changed:
        return "quality_changed"
    if not changed:
        return "steady"

    deltas = _numeric_deltas(previous, current)
    directions: list[int] = []
    for name in ("motion", "occupancy", "depth"):
        if name not in changed:
            continue
        delta = deltas[name]
        if delta == 0:
            order = {
                "motion": _MOTION_ORDER,
                "occupancy": _OCCUPANCY_ORDER,
                "depth": _DEPTH_ORDER,
            }[name]
            old = order.get(before[name])
            new = order.get(after[name])
            if old is None or new is None:
                return "shifted"
            delta = float((new > old) - (new < old))
        directions.append((delta > 0) - (delta < 0))
    if directions and all(value >= 0 for value in directions) and any(
        value > 0 for value in directions
    ):
        return "intensified"
    if directions and all(value <= 0 for value in directions) and any(
        value < 0 for value in directions
    ):
        return "eased"
    return "shifted"


def _comparison_summary(
    previous: EvidencePacket,
    current: EvidencePacket,
    relation: ContinuityRelation,
    changed: list[ChangedSignal],
) -> str:
    if relation == "steady":
        return "承接上一观点:三项代理的状态与主要数值未出现显著变化,继续观察是否形成持续节奏。"
    if relation == "recovered":
        return "修正上一观点:数据质量已恢复,可重新从当前三项代理建立受限解释。"
    if relation == "unknown":
        return "暂停递进:当前代理或质量进入未知状态,不沿用上一周期的确定性措辞。"

    before = _states(previous)
    after = _states(current)
    clauses = [
        _comparison_clause(name, previous, current, before, after)
        for name in changed
    ]
    prefix = {
        "intensified": "递进增强",
        "eased": "递进缓和",
        "shifted": "观点转折",
        "quality_changed": "质量边界改变",
    }.get(relation, "继续对照")
    return f"{prefix}:{';'.join(clauses)}。"


def _comparison_clause(
    name: ChangedSignal,
    previous: EvidencePacket,
    current: EvidencePacket,
    before: dict[ChangedSignal, str],
    after: dict[ChangedSignal, str],
) -> str:
    if before[name] != after[name]:
        label = {
            "motion": "活动",
            "occupancy": "占用",
            "depth": "纵深",
            "quality": "质量",
        }[name]
        return (
            f"{label}由{_STATE_LABELS.get(before[name], before[name])}变为"
            f"{_STATE_LABELS.get(after[name], after[name])}"
        )
    state_label = _STATE_LABELS.get(after[name], after[name])
    if name == "motion":
        return (
            f"活动仍为{state_label},强度由{previous.signals.motion.value:.2f}"
            f"变为{current.signals.motion.value:.2f}"
        )
    if name == "quality":
        return (
            f"质量仍为{state_label},传感置信上限由"
            f"{previous.signals.sensor_confidence_cap:.0%}变为"
            f"{current.signals.sensor_confidence_cap:.0%}"
        )
    if name == "occupancy":
        old_probability = getattr(
            previous.signals.occupancy_density.probabilities,
            before[name],
        )
        new_probability = getattr(
            current.signals.occupancy_density.probabilities,
            after[name],
        )
        return (
            f"占用仍为{state_label},对应概率由{old_probability:.0%}"
            f"变为{new_probability:.0%}"
        )
    old_probability = getattr(
        previous.signals.depth_zone.probabilities,
        before[name],
    )
    new_probability = getattr(
        current.signals.depth_zone.probabilities,
        after[name],
    )
    return (
        f"纵深仍为{state_label},对应概率由{old_probability:.0%}"
        f"变为{new_probability:.0%}"
    )
