"""Shared deterministic grounding for Mock, OpenAI, and DeepSeek providers.

Provider adapters contribute bounded prose. This module owns knowledge lookup,
evidence references, visible reasoning steps, and systematic readings so every
adapter is rebound to the same sealed EvidencePacket by a public API.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any, Literal, cast

from wifi_contracts import (
    AgentRole,
    AnalysisStep,
    EvidencePacket,
    ReadingLayer,
    SystematicReading,
)

from .outputs import SpatialLifeReaction

THEMED_ROLES: tuple[AgentRole, ...] = (
    "architecture",
    "biota",
    "feng_shui",
    "psyche",
    "soundscape",
)

_REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
_KNOWLEDGE_DIR = _REPOSITORY_ROOT / "data" / "knowledge"
_KNOWLEDGE_CACHE: dict[str, dict[str, Any]] = {}
_RULE_PAIR_RE = re.compile(r"([A-Za-z0-9_]+)\s*->\s*([^;]+)")

_ROLE_PHRASES: dict[str, dict[str, str]] = {
    "architecture": {
        "motion": "空间动线",
        "occupancy": "空间承载",
        "depth": "亲疏层级",
    },
    "biota": {
        "motion": "活动节律",
        "occupancy": "环境痕迹",
        "depth": "踪迹方向",
    },
    "feng_shui": {
        "motion": "气流意象",
        "occupancy": "气局意象",
        "depth": "明堂远近",
    },
    "psyche": {
        "motion": "空间心境",
        "occupancy": "被感知的在场感",
        "depth": "亲疏带",
    },
    "soundscape": {
        "motion": "声场前景事件",
        "occupancy": "声场纹理",
        "depth": "远近声场",
    },
}

_REASON_LINES = {
    "architecture": "空间分层与代理标量只构成相对关系,不是真实尺寸。",
    "biota": "只读取环境痕迹的强弱与疏密,不识别物种、个体或数量。",
    "feng_shui": "流、聚与远近只作文化叙事;标定或拓扑变化后需重新评估。",
    "psyche": "空间气质只作隐喻,不等同于任何人的心理状态。",
    "soundscape": "事件、纹理与远近是无声映射,不是麦克风或真实录音。",
}

_SCENE_IMAGES = {
    "architecture": "一张随代理状态改变的空间剖面",
    "biota": "一组只描述环境痕迹的节律",
    "feng_shui": "一场只用于叙事的空间呼吸",
    "psyche": "一条保护隐私的空间松紧带",
    "soundscape": "一段没有真实录音的空间节拍",
}

_NARRATIVE_OPENERS = {
    "architecture": "把三项代理连成一张空间剖面:",
    "biota": "把三个方向连成一段环境痕迹:",
    "feng_shui": "把当前三项代理连成一场文化隐喻:",
    "psyche": "把当前三项代理连成一条空间松紧带:",
    "soundscape": "把当前三项代理排成一段无声节拍:",
}

_NARRATIVE_CLOSERS = {
    "architecture": "这不是图纸,也不提供米制距离。",
    "biota": "这里只读痕迹,不认物种、个体或数量。",
    "feng_shui": "这不是占卜或命运判断,只是文化叙事。",
    "psyche": "这不是对任何人的心理诊断。",
    "soundscape": "这是声景隐喻,不是真实录音。",
}

_BOUNDARY_NOTES = {
    "architecture": ["相对空间层级不提供米制距离。", "不识别具体使用者。"],
    "biota": ["环境痕迹不等于个体存在。", "不识别物种、个体或数量。"],
    "feng_shui": ["气、明堂与吉凶均为文化隐喻。", "不产生或改变测量值。"],
    "psyche": ["空间气质不是心理诊断。", "真实心理状态需要知情同意。"],
    "soundscape": ["声景映射不是真实声音。", "真实声学需要独立传感与校准。"],
}

_MULTIMODAL_HINTS = {
    "architecture": ["可用独立布局或深度传感器对照相对层级,并建立新标定。"],
    "biota": ["可用独立环境模态离线对照痕迹隐喻,仍不识别个体。"],
    "feng_shui": ["可用温湿度或光照模态对照文化意象,仍不作为测量结论。"],
    "psyche": ["可用知情同意后的问卷对照空间体验描述。"],
    "soundscape": ["可用独立校准的声学模态对照节奏映射。"],
}


def evidence_ref(packet: EvidencePacket, path: str) -> str:
    """Return one evidence URI tied to the packet's immutable hash."""
    return f"evidence://{packet.evidence_hash}/{path}"


def stable_index(packet: EvidencePacket, role: str, salt: str = "") -> int:
    """Select deterministic role knowledge without global random state."""
    digest = hashlib.sha256(
        f"{packet.evidence_hash}:{role}:{salt}".encode()
    ).hexdigest()
    return int(digest[:8], 16)


def load_role_knowledge(role: str) -> dict[str, Any]:
    """Load one curated role knowledge file from a cwd-independent path."""
    if role not in _KNOWLEDGE_CACHE:
        path = _KNOWLEDGE_DIR / f"{role}.json"
        if path.is_file():
            _KNOWLEDGE_CACHE[role] = json.loads(path.read_text(encoding="utf-8"))
        else:
            _KNOWLEDGE_CACHE[role] = {"entries": []}
    return _KNOWLEDGE_CACHE[role]


def context_refs(packet: EvidencePacket) -> list[str]:
    """Return the four mandatory compact evidence references."""
    return [
        evidence_ref(packet, "signals/motion/state"),
        evidence_ref(packet, "signals/occupancy/state"),
        evidence_ref(packet, "signals/depth/state"),
        evidence_ref(packet, "quality/overall_status"),
    ]


def scene_decision(packet: EvidencePacket) -> Literal[
    "save_candidate", "compare_next", "unknown"
]:
    """Apply the shared quality gate before any themed interpretation."""
    states = (
        packet.signals.motion.state,
        packet.signals.occupancy_density.state,
        packet.signals.depth_zone.state,
    )
    if packet.quality.overall_status in ("insufficient_signal", "uncalibrated"):
        return "unknown"
    if "unknown" in states:
        return "unknown"
    if packet.quality.overall_status == "degraded" or packet.quality.quality_flags:
        return "compare_next"
    return "save_candidate"


def build_analysis_steps(
    *,
    packet: EvidencePacket,
    role: str,
    entries: list[dict[str, Any]],
    primary: dict[str, Any],
    other: dict[str, Any],
    proposition: str,
) -> list[AnalysisStep]:
    """Build the public five-step trace without exposing hidden reasoning."""
    signals = packet.signals
    signal_refs = [
        evidence_ref(packet, "signals/motion/state"),
        evidence_ref(packet, "signals/occupancy/state"),
        evidence_ref(packet, "signals/depth/state"),
    ]
    quality_refs = [
        evidence_ref(packet, "quality/overall_status"),
        evidence_ref(packet, "quality/packet_coverage"),
    ]
    mappings = _signal_rules(entries, signals)
    return [
        AnalysisStep(
            step_id="observe",
            phase="observe",
            title="观察信号",
            text=(
                f"读取证据包标量: motion={signals.motion.state}, "
                f"occupancy={signals.occupancy_density.state}, "
                f"depth={signals.depth_zone.state}, "
                f"quality={packet.quality.overall_status};只引用 sealed 代理字段。"
            ),
            evidence_refs=[
                *signal_refs,
                evidence_ref(packet, "quality/overall_status"),
            ],
        ),
        AnalysisStep(
            step_id="retrieve",
            phase="retrieve",
            title="检索知识库",
            text=(
                f"命中主概念『{primary.get('concept', '空间')}』"
                f"({primary.get('source', '')});备用视角『{other.get('concept', '')}』。"
            ),
            evidence_refs=list(quality_refs),
        ),
        AnalysisStep(
            step_id="map",
            phase="map",
            title="意象映射",
            text=(
                "; ".join(mappings)
                if mappings
                else "知识规则无直接映射,按角色边界保持受限解读。"
            ),
            evidence_refs=list(signal_refs),
        ),
        AnalysisStep(
            step_id="reason",
            phase="reason",
            title="推理",
            text=_REASON_LINES.get(
                role,
                "标定与拓扑不变是映射前提,且解释不能改变数值。",
            ),
            evidence_refs=list(quality_refs),
        ),
        AnalysisStep(
            step_id="conclude",
            phase="conclude",
            title="结论",
            text=f"收敛为命题: {proposition}",
            evidence_refs=list(signal_refs),
        ),
    ]


def build_systematic_reading(
    *,
    packet: EvidencePacket,
    role: str,
    entries: list[dict[str, Any]],
    reaction: SpatialLifeReaction,
    proposition: str,
) -> SystematicReading:
    """Build a role-voiced, three-layer interpretation of one sealed triplet."""
    layers: list[ReadingLayer] = []
    explanations: list[str] = []
    for signal_name, state, metaphor in _signal_readings(
        entries, packet, role, reaction
    ):
        scene_word = {
            "motion": reaction.motion,
            "occupancy": reaction.occupancy,
            "depth": reaction.depth,
        }[signal_name]
        explanation = _layer_explanation(role, signal_name, state, scene_word)
        layers.append(
            ReadingLayer(
                signal=signal_name,
                state=state,
                metaphor=metaphor,
                explanation=explanation,
            )
        )
        explanations.append(explanation)
    opener = _NARRATIVE_OPENERS.get(role, "综合三种标量:")
    closer = _NARRATIVE_CLOSERS.get(role, "以上均为隐喻解读,不等于测量。")
    return SystematicReading(
        headline=proposition,
        scene_sketch=(
            "空间生命体反应(叙事隐喻,不表示真实生命或意识):"
            f"{reaction.render()};像{_SCENE_IMAGES.get(role, '一幅变化的空间意象')}。"
        ),
        layers=layers,
        narrative=f"{opener} {' '.join(explanations)} {closer}",
        boundary_notes=_BOUNDARY_NOTES.get(
            role, ["本解读为隐喻,不改变任何测量值。"]
        ),
        multimodal_hints=_MULTIMODAL_HINTS.get(role, []),
    )


def _rule_map(entry: dict[str, Any]) -> dict[str, str]:
    return {
        key.strip(): value.strip()
        for key, value in _RULE_PAIR_RE.findall(str(entry.get("rule", "")))
    }


def _signal_rules(entries: list[dict[str, Any]], signals: Any) -> list[str]:
    mappings: list[str] = []
    for attr, key in (
        ("motion", "motion"),
        ("occupancy_density", "occupancy"),
        ("depth_zone", "depth"),
    ):
        state = getattr(signals, attr).state
        state_key = f"{key}_{state}"
        for entry in entries:
            rule = _rule_map(entry).get(state_key)
            if rule:
                mappings.append(f"{state_key} -> {rule}")
                break
    return mappings


def _signal_readings(
    entries: list[dict[str, Any]],
    packet: EvidencePacket,
    role: str,
    reaction: SpatialLifeReaction,
) -> list[tuple[Literal["motion", "occupancy", "depth"], str, str]]:
    readings: list[
        tuple[Literal["motion", "occupancy", "depth"], str, str]
    ] = []
    for attr, key in (
        ("motion", "motion"),
        ("occupancy_density", "occupancy"),
        ("depth_zone", "depth"),
    ):
        state = getattr(packet.signals, attr).state
        state_key = f"{key}_{state}"
        metaphor = next(
            (
                value
                for entry in entries
                if (value := _rule_map(entry).get(state_key))
            ),
            "",
        )
        reaction_word = {
            "motion": reaction.motion,
            "occupancy": reaction.occupancy,
            "depth": reaction.depth,
        }[key]
        fallback = f"{_ROLE_PHRASES.get(role, {}).get(key, '空间意象')}{reaction_word}"
        readings.append(
            (
                cast(Literal["motion", "occupancy", "depth"], key),
                state,
                metaphor or fallback,
            )
        )
    return readings


def _layer_explanation(role: str, signal: str, state: str, scene_word: str) -> str:
    phrase = _ROLE_PHRASES.get(role, {}).get(signal, "空间意象")
    if signal == "motion":
        return f"{phrase}读作「{scene_word}」:只描述代理变化,不是个体动作。"
    if signal == "occupancy":
        return f"{phrase}读作「{scene_word}」:只描述遮挡与充盈度,不是人数。"
    return (
        f"{phrase}读作「{scene_word}」:纵深是相对层级,不是米制距离,"
        f"当前状态为 {state}。"
    )
