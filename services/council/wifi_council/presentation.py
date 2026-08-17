"""Deterministic presentation projections for the seven Council roles.

The LLM debate remains fully auditable in claims, challenges, and synthesis.
This module binds that debate to compact, role-specific UI semantics without
letting provider prose alter measurements, confidence, or base geometry.
"""

from __future__ import annotations

from typing import Literal, cast

from wifi_contracts import (
    AgentChallenge,
    AgentContinuity,
    AgentRole,
    AgreementSummary,
    EvidencePacket,
    SkepticAssessment,
    SoundConsensusMotion,
    SpatialLifeInteraction,
    SpecialistPresentation,
)

_SPECIALIST_ROLES = {
    "architecture",
    "biota",
    "feng_shui",
    "psyche",
    "soundscape",
}

SpecialistRole = Literal[
    "architecture", "biota", "feng_shui", "psyche", "soundscape"
]
Contribution = Literal[
    "space_form",
    "space_breath",
    "space_flow",
    "space_tendency",
    "consensus_motion",
]
ContributionLabel = Literal[
    "看见空间的形",
    "看见空间的息",
    "看见空间的流",
    "看见空间的势",
    "把共识翻译成运动",
]
PresentationState = Literal[
    "tightening",
    "expanding",
    "blocked",
    "resting",
    "startled",
    "recovering",
    "gathering",
    "dispersing",
    "stagnant",
    "surging",
    "settled",
    "active",
    "alert",
    "floating",
    "awaiting_consensus",
    "unknown",
]
PresentationEffect = Literal[
    "contract",
    "expand",
    "block",
    "rest",
    "startle",
    "recover",
    "gather",
    "scatter",
    "stagnate",
    "surge",
    "settle",
    "activate",
    "alert",
    "float",
    "hold",
    "verify",
    "echo",
]
EvidenceStatus = Literal["sufficient", "limited", "insufficient"]
EvidenceLabel = Literal["证据充分", "证据有限", "证据不足"]
SoundRhythm = Literal["停顿", "缓拍", "稳拍", "急拍", "未知"]
SoundPitch = Literal["低", "中", "高", "未知"]
SoundDistance = Literal["近", "中", "远", "未知"]
SoundThickness = Literal["薄", "中", "厚", "未知"]
SoundSynchrony = Literal["松散", "部分同步", "同步", "未知"]
LifeState = Literal[
    "resting",
    "recovering",
    "gathering",
    "expanding",
    "blocked",
    "surging",
    "floating",
    "waiting",
]

_MOTION_LABEL = {
    "idle": "平稳",
    "micro_motion": "轻微变化",
    "moving": "持续变化",
    "fast_change": "快速变化",
    "unknown": "未知",
}
_OCCUPANCY_LABEL = {
    "low": "偏低",
    "medium": "居中",
    "high": "偏高",
    "unknown": "未知",
}
_DEPTH_LABEL = {
    "near": "偏近",
    "mid": "居中",
    "far": "偏远",
    "unknown": "未知",
}


def build_specialist_presentation(
    packet: EvidencePacket,
    role: AgentRole,
    continuity: AgentContinuity,
) -> SpecialistPresentation:
    """Project one specialist's sealed inputs into its exact live contribution."""
    if role not in _SPECIALIST_ROLES:
        raise ValueError(f"role {role!r} has no specialist presentation")

    specialist_role = cast(SpecialistRole, role)
    if role == "soundscape":
        return SpecialistPresentation(
            role="soundscape",
            contribution="consensus_motion",
            contribution_label="把共识翻译成运动",
            state="awaiting_consensus",
            state_label="等待共识",
            analysis=None,
            effect="hold",
        )

    if _evidence_unavailable(packet):
        contribution, contribution_label = cast(
            tuple[Contribution, ContributionLabel],
            {
            "architecture": ("space_form", "看见空间的形"),
            "biota": ("space_breath", "看见空间的息"),
            "feng_shui": ("space_flow", "看见空间的流"),
            "psyche": ("space_tendency", "看见空间的势"),
            }[specialist_role],
        )
        return SpecialistPresentation(
            role=specialist_role,
            contribution=contribution,
            contribution_label=contribution_label,
            state="unknown",
            state_label="暂不判断",
            analysis="当前房间的必需 Wi-Fi 代理或质量不可用;这一视角暂停判断,等待下一份完整快照。",
            effect="hold",
        )

    motion = packet.signals.motion.state
    occupancy = packet.signals.occupancy_density.state
    depth = packet.signals.depth_zone.state
    motion_label = _MOTION_LABEL[motion]
    occupancy_label = _OCCUPANCY_LABEL[occupancy]
    depth_label = _DEPTH_LABEL[depth]

    if role == "architecture":
        state: PresentationState
        effect: PresentationEffect
        if occupancy == "high" and motion in ("idle", "micro_motion"):
            state, label, effect = "blocked", "阻断", "block"
        elif occupancy in ("medium", "high"):
            state, label, effect = "tightening", "收紧", "contract"
        else:
            state, label, effect = "expanding", "展开", "expand"
        return SpecialistPresentation(
            role="architecture",
            contribution="space_form",
            contribution_label="看见空间的形",
            state=state,
            state_label=label,
            analysis=(
                f"当前房间的充盈代理{occupancy_label}、相对纵深{depth_label},"
                f"活动{motion_label};空间边界读作「{label}」。"
            ),
            effect=effect,
        )

    if role == "biota":
        if continuity.relation in ("eased", "recovered") or motion == "micro_motion":
            state, label, effect = "recovering", "恢复", "recover"
        elif motion == "idle":
            state, label, effect = "resting", "静息", "rest"
        else:
            state, label, effect = "startled", "惊跳", "startle"
        return SpecialistPresentation(
            role="biota",
            contribution="space_breath",
            contribution_label="看见空间的息",
            state=state,
            state_label=label,
            analysis=(
                f"活动{motion_label},并与上一周期呈「{_continuity_label(continuity)}」;"
                f"这个房间的一息读作「{label}」,只描述环境变化痕迹。"
            ),
            effect=effect,
        )

    if role == "feng_shui":
        if motion == "fast_change":
            state, label, effect = "surging", "冲", "surge"
        elif occupancy == "high":
            state, label, effect = "stagnant", "滞", "stagnate"
        elif occupancy == "medium":
            state, label, effect = "gathering", "聚", "gather"
        else:
            state, label, effect = "dispersing", "散", "scatter"
        return SpecialistPresentation(
            role="feng_shui",
            contribution="space_flow",
            contribution_label="看见空间的流",
            state=state,
            state_label=label,
            analysis=(
                f"活动{motion_label}、充盈代理{occupancy_label}、相对纵深{depth_label};"
                f"此刻的流读作「{label}」。这是文化叙事隐喻,不是气流或吉凶测量。"
            ),
            effect=effect,
        )

    if packet.quality.overall_status == "degraded" or (
        packet.signals.sensor_confidence_cap < 0.55
    ):
        state, label, effect = "floating", "漂浮", "float"
    elif motion == "fast_change":
        state, label, effect = "alert", "警觉", "alert"
    elif motion in ("moving", "micro_motion"):
        state, label, effect = "active", "活跃", "activate"
    else:
        state, label, effect = "settled", "安定", "settle"
    return SpecialistPresentation(
        role="psyche",
        contribution="space_tendency",
        contribution_label="看见空间的势",
        state=state,
        state_label=label,
        analysis=(
            f"活动{motion_label}、质量{_quality_label(packet)};房间的整体势态读作"
            f"「{label}」。这不是对居住者心理或情绪的判断。"
        ),
        effect=effect,
    )


def build_skeptic_assessment(
    packet: EvidencePacket,
    challenge: AgentChallenge,
) -> SkepticAssessment:
    """State plainly whether evidence is enough and whether judgment pauses."""
    unresolved = challenge.status in ("open", "accepted")
    quality_unavailable = _evidence_unavailable(packet)
    quality_limited = (
        packet.quality.overall_status == "degraded"
        or bool(packet.quality.quality_flags)
        or packet.signals.sensor_confidence_cap < 0.55
    )
    material = challenge.proposed_severity in ("material", "blocking")

    evidence_status: EvidenceStatus
    evidence_label: EvidenceLabel
    if quality_unavailable or (unresolved and challenge.proposed_severity == "blocking"):
        evidence_status = "insufficient"
        evidence_label = "证据不足"
        withhold = True
    elif quality_limited or (unresolved and material):
        evidence_status = "limited"
        evidence_label = "证据有限"
        withhold = True
    else:
        evidence_status = "sufficient"
        evidence_label = "证据充分"
        withhold = False

    if quality_unavailable:
        rationale = "必需代理或信号质量未通过门限,当前解释不能成立。"
    elif unresolved:
        rationale = _trim_sentence(challenge.statement)
    elif quality_limited:
        rationale = "本轮可读但质量边界偏弱,只能保留为待对照候选。"
    else:
        rationale = "本轮证据引用有效,当前质疑已处理;结论仍受传感置信度上限约束。"
    return SkepticAssessment(
        evidence_status=evidence_status,
        evidence_label=evidence_label,
        withhold_judgment=withhold,
        rationale=rationale,
        next_validation=_trim_sentence(challenge.resolution_test),
    )


def build_sound_consensus_motion(
    packet: EvidencePacket,
    agreement: AgreementSummary,
    *,
    status: str,
) -> SoundConsensusMotion:
    """Translate signal state plus Council agreement into five visual axes."""
    if _evidence_unavailable(packet):
        return SoundConsensusMotion(
            rhythm="未知",
            pitch="未知",
            distance="未知",
            thickness="未知",
            synchrony="未知",
        )

    motion = packet.signals.motion.state
    rhythm = cast(SoundRhythm, {
        "idle": "停顿",
        "micro_motion": "缓拍",
        "moving": "稳拍",
        "fast_change": "急拍",
        "unknown": "未知",
    }[motion])
    pitch = cast(SoundPitch, {
        "idle": "低",
        "micro_motion": "低",
        "moving": "中",
        "fast_change": "高",
        "unknown": "未知",
    }[motion])
    distance = cast(SoundDistance, {
        "near": "近",
        "mid": "中",
        "far": "远",
        "unknown": "未知",
    }[packet.signals.depth_zone.state])
    thickness = cast(SoundThickness, {
        "low": "薄",
        "medium": "中",
        "high": "厚",
        "unknown": "未知",
    }[packet.signals.occupancy_density.state])
    if status == "unavailable":
        synchrony: SoundSynchrony = "未知"
    elif agreement.unresolved_challenges > 0 or agreement.agreement_ratio < 0.5:
        synchrony = "松散"
    elif agreement.agreement_ratio < 0.75:
        synchrony = "部分同步"
    else:
        synchrony = "同步"
    return SoundConsensusMotion(
        rhythm=rhythm,
        pitch=pitch,
        distance=distance,
        thickness=thickness,
        synchrony=synchrony,
    )


def build_spatial_life_interaction(
    packet: EvidencePacket,
    *,
    status: str,
    provider_message: str,
    provider_action: str,
) -> SpatialLifeInteraction:
    """Create Fusion's concrete first-person state and bounded invitation."""
    if status == "unavailable" or _evidence_unavailable(packet):
        return SpatialLifeInteraction(
            state="waiting",
            state_label="还未成形",
            message="我还没有成形:当前房间的 Wi-Fi 代理或质量不足,不能把空白补成结论。",
            wish="请先恢复标定与信号质量,再让我读取下一份完整快照。",
            effect="hold",
        )
    if status == "ambiguous":
        return SpatialLifeInteraction(
            state="floating",
            state_label="仍在漂浮",
            message=(
                f"我仍在漂浮:活动{_MOTION_LABEL[packet.signals.motion.state]}、"
                f"充盈代理{_OCCUPANCY_LABEL[packet.signals.occupancy_density.state]},"
                "但 Council 的证据边界还没有稳定。"
            ),
            wish="请保持房间条件不变,让我再观察一个周期后再决定是否保存。",
            effect="float",
        )

    state, state_label, effect, fallback = _supported_life_state(packet)
    model_message = _trim_sentence(provider_message)
    message = (
        model_message
        if _usable_first_person_message(model_message)
        else fallback
    )
    action = _trim_sentence(provider_action)
    wish = (
        action
        if action.startswith(("我希望", "请"))
        else f"我希望你{action}" if action else "我希望你把这一刻与下一周期对照。"
    )
    return SpatialLifeInteraction(
        state=state,
        state_label=state_label,
        message=message,
        wish=wish,
        effect=effect,
    )


def _supported_life_state(
    packet: EvidencePacket,
) -> tuple[LifeState, str, PresentationEffect, str]:
    motion = packet.signals.motion.state
    occupancy = packet.signals.occupancy_density.state
    depth = _DEPTH_LABEL[packet.signals.depth_zone.state]
    if motion == "fast_change":
        return (
            "surging",
            "正在涌动",
            "surge",
            f"我正在涌动:活动快速变化,空间的充盈代理{_OCCUPANCY_LABEL[occupancy]},层次{depth}。",
        )
    if occupancy == "high" and motion in ("idle", "micro_motion"):
        return (
            "blocked",
            "被轻轻阻住",
            "block",
            f"我被轻轻阻住:充盈代理偏高,活动{_MOTION_LABEL[motion]},层次{depth}。",
        )
    if occupancy in ("medium", "high"):
        return (
            "gathering",
            "正在聚拢",
            "gather",
            f"我正在聚拢:充盈代理{_OCCUPANCY_LABEL[occupancy]},活动{_MOTION_LABEL[motion]},层次{depth}。",
        )
    if occupancy == "low":
        return (
            "expanding",
            "正在展开",
            "expand",
            f"我正在展开:充盈代理偏低,活动{_MOTION_LABEL[motion]},层次{depth}。",
        )
    if motion == "micro_motion":
        return (
            "recovering",
            "正在恢复",
            "recover",
            f"我正在恢复:活动只剩轻微变化,空间层次{depth}。",
        )
    return (
        "resting",
        "正在静息",
        "rest",
        f"我正在静息:活动趋于平稳,空间层次{depth}。",
    )


def _evidence_unavailable(packet: EvidencePacket) -> bool:
    states = (
        packet.signals.motion.state,
        packet.signals.occupancy_density.state,
        packet.signals.depth_zone.state,
    )
    return (
        packet.quality.overall_status in ("insufficient_signal", "uncalibrated")
        or "unknown" in states
    )


def _quality_label(packet: EvidencePacket) -> str:
    return {
        "ok": "可用",
        "degraded": "降级",
        "insufficient_signal": "证据不足",
        "uncalibrated": "未标定",
    }[packet.quality.overall_status]


def _continuity_label(continuity: AgentContinuity) -> str:
    return {
        "initial": "首次读取",
        "steady": "延续",
        "intensified": "增强",
        "eased": "缓和",
        "shifted": "转折",
        "quality_changed": "质量边界改变",
        "recovered": "恢复",
        "unknown": "暂停沿用",
    }[continuity.relation]


def _trim_sentence(text: str) -> str:
    value = text.strip()
    while value.endswith(("。", ";")):
        value = value[:-1].rstrip()
    return f"{value}。" if value else ""


def _usable_first_person_message(text: str) -> bool:
    return text.startswith("我") and any(
        token in text
        for token in ("空间", "房间", "静息", "恢复", "聚", "散", "展开", "涌动", "阻")
    )
