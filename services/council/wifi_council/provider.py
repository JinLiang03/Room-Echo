"""AgentProvider protocol with deterministic Mock and optional OpenAI providers.

Providers return structured Pydantic outputs (Structured Outputs) — never
free-text JSON parsing. The mock is a genuinely testable council: it abstains
on single-RX depth, raises a material confound under interference, and can
emit controlled bad outputs for policy tests. The OpenAI provider reads the
API key only from the server environment and reports health without ever
exposing credentials.
"""

from __future__ import annotations

import asyncio
import copy
import hashlib
import json
import os
import re
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Generic, Literal, Protocol, TypeVar, cast, runtime_checkable

from wifi_contracts import (
    AgentChallenge,
    AgentClaim,
    AgentRole,
    AnalysisStep,
    EvidencePacket,
    ProviderHealth,
    ReadingLayer,
    SystematicReading,
)

from .config import CouncilConfig
from .outputs import (
    AgentChallengeOutput,
    ApprovedCouncilInput,
    ChallengeSet,
    ResponseOutput,
    SpecialistProposal,
    SynthesisOutput,
)
from .prompts import PromptVersion

T = TypeVar("T")

CallStatus = Literal["ok", "timeout", "error", "offline", "cache_hit"]
Misbehavior = Literal["none", "bad_refs", "overreach", "fabricated_number", "old_hash"]


@dataclass(frozen=True)
class ProviderCall(Generic[T]):
    """One provider attempt with observable usage; never contains secrets."""

    value: T | None
    model: str
    latency_ms: int
    input_tokens: int = 0
    output_tokens: int = 0
    status: CallStatus = "ok"
    cache_hit: bool = False
    trace_id: str | None = None
    error: str | None = None


@runtime_checkable
class AgentProvider(Protocol):
    """Interface from AGENT_COUNCIL.md section 6."""

    name: str
    model: str

    async def propose(
        self,
        role: AgentRole,
        packet: EvidencePacket,
        prompt: PromptVersion,
    ) -> ProviderCall[SpecialistProposal]: ...

    async def challenge(
        self,
        packet: EvidencePacket,
        claims: list[AgentClaim],
        prompt: PromptVersion,
    ) -> ProviderCall[ChallengeSet]: ...

    async def respond(
        self,
        packet: EvidencePacket,
        claim: AgentClaim,
        challenges: list[AgentChallenge],
        prompt: PromptVersion,
    ) -> ProviderCall[ResponseOutput]: ...

    async def synthesize(
        self,
        approved: ApprovedCouncilInput,
        prompt: PromptVersion,
    ) -> ProviderCall[SynthesisOutput]: ...

    def health(self) -> ProviderHealth: ...


def _ref(packet: EvidencePacket, path: str) -> str:
    return f"evidence://{packet.evidence_hash}/{path}"


def _stable_index(packet: EvidencePacket, role: str, salt: str = "") -> int:
    digest = hashlib.sha256(
        f"{packet.evidence_hash}:{role}:{salt}".encode()
    ).hexdigest()
    return int(digest[:8], 16)


THEMED_ROLES: tuple[AgentRole, ...] = (
    "architecture",
    "biota",
    "feng_shui",
    "psyche",
    "soundscape",
)

KNOWLEDGE_DIR = Path("data/knowledge")
_knowledge_cache: dict[str, dict[str, Any]] = {}


def _load_knowledge(role: str) -> dict[str, Any]:
    if role not in _knowledge_cache:
        path = KNOWLEDGE_DIR / f"{role}.json"
        if path.is_file():
            _knowledge_cache[role] = json.loads(path.read_text(encoding="utf-8"))
        else:
            _knowledge_cache[role] = {"entries": []}
    return _knowledge_cache[role]


def _scene_words(signals: Any) -> dict[str, str]:
    """Map signal states to vivid Chinese scene words (deterministic)."""
    energy = {
        "idle": "静",
        "micro_motion": "微动",
        "moving": "流动",
        "fast_change": "翻涌",
        "unknown": "不明",
    }
    occ = {
        "low": "疏朗",
        "medium": "渐聚",
        "high": "充盈",
        "unknown": "不明",
    }
    depth = {
        "near": "近前",
        "mid": "中景",
        "far": "远处",
        "unknown": "不明",
    }
    return {
        "energy": energy.get(signals.motion.state, "不明"),
        "occ": occ.get(signals.occupancy_density.state, "不明"),
        "deep": depth.get(signals.depth_zone.state, "不明"),
    }


_SIMILES: dict[str, list[str]] = {
    "feng_shui": ["刚落定的棋局", "雨后的庭院", "拢住的一口井"],
    "architecture": ["一页摊开的剖面图", "刚清场的中庭", "走完一圈的环形走廊"],
    "biota": ["雨后林间的足迹", "潮水退去的滩涂", "夜里亮起的萤火"],
    "psyche": ["有人刚坐下又起身", "窗帘被风撩了一下", "灯下翻过一页书"],
    "soundscape": ["远处教堂的钟声", "清晨的市集", "夜航的汽笛"],
}


_RULE_PAIR_RE = re.compile(r"([A-Za-z0-9_]+)\s*->\s*([^;]+)")


def _rule_map(entry: dict[str, Any]) -> dict[str, str]:
    """Parse `signal_state -> 意象` pairs from a knowledge entry rule."""
    return {
        key.strip(): value.strip()
        for key, value in _RULE_PAIR_RE.findall(str(entry.get("rule", "")))
    }


def _signal_rules(
    entries: list[dict[str, Any]],
    signals: Any,
) -> list[str]:
    """Deterministic per-signal metaphor mapping using the knowledge rules."""
    mappings: list[str] = []
    for attr, key in (
        ("motion", "motion"),
        ("occupancy_density", "occupancy"),
        ("depth_zone", "depth"),
    ):
        state = getattr(signals, attr).state
        state_key = f"{key}_{state}"
        for entry in entries:
            rules = _rule_map(entry)
            if state_key in rules:
                mappings.append(f"{state_key} -> {rules[state_key]}")
                break
    return mappings


def _signal_readings(
    entries: list[dict[str, Any]],
    signals: Any,
) -> list[tuple[Literal["motion", "occupancy", "depth"], str, str]]:
    """Structured per-signal metaphor readings, deterministic from KB rules."""
    readings: list[tuple[Literal["motion", "occupancy", "depth"], str, str]] = []
    for attr, key in (
        ("motion", "motion"),
        ("occupancy_density", "occupancy"),
        ("depth_zone", "depth"),
    ):
        state = getattr(signals, attr).state
        state_key = f"{key}_{state}"
        metaphor = ""
        for entry in entries:
            rules = _rule_map(entry)
            if state_key in rules:
                metaphor = rules[state_key]
                break
        readings.append(
            (
                cast(Literal["motion", "occupancy", "depth"], key),
                state,
                metaphor or "意象不明",
            )
        )
    return readings


_REASON_LINES: dict[str, str] = {
    "feng_shui": (
        "把三种标量读成同一场气的三种侧面:流、聚、远近。"
        "这个读法成立的前提是标定与拓扑未变;若换了房间或注入干扰,意象需要重新评估。"
    ),
    "architecture": (
        "近体学与剖面图都是把空间分层的方式,和标量代理同构。"
        "我读的是层级关系,不是真实尺寸;任何米制读数都需要硬件测量,不在我的视野内。"
    ),
    "biota": (
        "我只认活动痕迹的强弱与疏密,不认物种也不认个体。"
        "被动感知的类比意味着:痕迹多不等于有人,痕迹少也不等于无人。"
    ),
    "psyche": (
        "心境、亲疏带、在场感都是隐喻,不是心理测量。"
        "真正的心理状态需要问卷与知情同意,这里只呈现空间被感知的气质。"
    ),
    "soundscape": (
        "声场理论把事件、基调与远近分开;这里的标量是空间代理,不是麦克风。"
        "所以这是声景的隐喻,不是真实声音。"
    ),
}


_ROLE_PHRASES: dict[str, dict[str, str]] = {
    "feng_shui": {
        "motion": "气流意象",
        "occupancy": "气局意象",
        "depth": "明堂远近",
    },
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


_SCENE_SKETCH: dict[str, str] = {
    "feng_shui": (
        "如果此刻有风,它会在近前慢慢转向;空气带着疏朗的密度,"
        "安静得像一场刚醒的呼吸。气不急着聚,也不急着散,"
        "整个房间像一张还没落定的棋局。"
    ),
    "architecture": (
        "把房间想象成一张正在摊开的剖面图:动线松弛,体量疏朗,"
        "空间层级停在近前的位置。中庭刚清过场,四壁和地面的关系"
        "都还在彼此试探。"
    ),
    "biota": (
        "像雨后的林间空地:地面有活动的痕迹,却不密集,方向停留在近前。"
        "我不知道是什么留下的,只知道此刻的扰动还没有铺开。"
    ),
    "psyche": (
        "这个空间此刻的气质是安静的:有人坐过的痕迹很轻,在场感不浓,"
        "亲疏带落在近前。像窗帘被风撩了一下,又落回原处。"
    ),
    "soundscape": (
        "声场很干净:基调平稳,纹理疏朗,近处有一个还未展开的前景事件。"
        "像清晨的市集刚开张,远处还有教堂钟声的回音。"
    ),
}


_NARRATIVE_OPENER: dict[str, str] = {
    "feng_shui": "按青禾的读法,这间房的气是缓的、散的、近的:",
    "architecture": "筑间把这三件事连成一张剖面:",
    "biota": "蕨把三个方向收进一片林间空地:",
    "psyche": "澄在心里给这个空间画了一张心境图:",
    "soundscape": "汐把它当作一段还很少人听见的声景:",
}


_NARRATIVE_CLOSER: dict[str, str] = {
    "feng_shui": "这不是占卜,也不是对命运的判断;只是把标量读成一场呼吸。",
    "architecture": "这只是一张意象图,不是真正的图纸,也不提供米制距离。",
    "biota": "我只读痕迹,不认物种,也不认数量。",
    "psyche": "这是空间被感知的气质,不是任何人的心理诊断。",
    "soundscape": "这是声景的隐喻,不是真实的录音。",
}


_BOUNDARY_NOTES: dict[str, list[str]] = {
    "feng_shui": [
        "气、明堂、吉凶都是文化隐喻,不代表真实气流或运势。",
        "本解读不产生任何测量值,也不改变传感器置信。",
        "标定或拓扑变化后,意象需要重新评估。",
    ],
    "architecture": [
        "空间层级是相对代理,不提供米制距离。",
        "动线与体量读法不识别具体使用者。",
    ],
    "biota": [
        "痕迹多不等于有生物个体,痕迹少也不等于无。",
        "不识别物种、个体或人数。",
    ],
    "psyche": [
        "空间心境是被感知的气质隐喻,不是心理诊断。",
        "真实心理状态需要问卷与知情同意。",
    ],
    "soundscape": [
        "这是声景的隐喻,不是真实声音测量。",
        "真实声学需要麦克风与独立校准。",
    ],
}


_MULTIMODAL_HINTS: dict[str, list[str]] = {
    "feng_shui": [
        "若接入声学模态,可对照环境声级与“气动”意象是否一致,但需独立标定。",
        "若接入温湿度/光照模态,可验证风感意象与通风条件的相关性;仍属隐喻对照。",
    ],
    "architecture": [
        "若接入占用布局图(仅标注遮挡方向,不做个体识别),可校验空间承载读法。",
        "若接入独立深度传感器,可建立相对层级的对照,但需新的标定 profile。",
    ],
    "biota": [
        "若接入被动声学(环境声),可丰富“存在-活动场”意象,不识别个体。",
        "若接入环境采样结果,可作为离线证据对照痕迹隐喻,而非实时测量。",
    ],
    "psyche": [
        "若接入停留时长统计,可验证亲疏带意象的分布趋势。",
        "若接入问卷访谈(需知情同意),可对照“空间心境”的体验描述。",
    ],
    "soundscape": [
        "若接入真实麦克风,可把“声场事件”从隐喻升级为可测声级,但需独立校准与隐私评估。",
        "若接入振动/结构声传感器,可对照低频纹理意象。",
    ],
}


def _layer_explanation(role: str, signal: str, state: str, scene_word: str) -> str:
    phrase = _ROLE_PHRASES.get(role, {}).get(signal, "空间意象")
    if signal == "motion":
        return (
            f"{phrase}读作「{scene_word}」:运动标量描述的是代理变化,"
            "不是任何个体的具体动作。"
        )
    if signal == "occupancy":
        return (
            f"{phrase}读作「{scene_word}」:占用密度描述遮挡与空间充盈度,"
            "不是人数。"
        )
    return (
        f"{phrase}读作「{scene_word}」:纵深是相对层级,不是米制距离,"
        f"当前状态为 {state}。"
    )


def _vivid_narrative(
    role: str,
    scene: dict[str, str],
    index: int,
    persona: dict[str, Any],
    primary: dict[str, Any],
) -> str:
    """Persona-voiced, deterministic vivid interpretation (metaphor)."""
    name = persona.get("name", role)
    concept = primary.get("concept", "空间")
    similes = _SIMILES.get(role, ["一幅流动的画卷"])
    simile = similes[index % len(similes)]
    energy, occ, deep = scene["energy"], scene["occ"], scene["deep"]
    if role == "feng_shui":
        body = (
            f"此刻的空间像一场缓慢的呼吸:气流{energy},气局{occ},"
            f"明堂落在{deep}. 气聚而不滞,藏风而有序,仿佛{simile}."
        )
    elif role == "architecture":
        body = (
            f"如果把这里当作一张剖面图:动线{energy},体量{occ},"
            f"空间层级停在{deep}的位置. 近体学上说,这像{simile}."
        )
    elif role == "biota":
        body = (
            f"像一片林间空地:活动的痕迹{energy},存在的密度{occ},"
            f"方向在{deep}. 我只读痕迹,不认物种——这像{simile}."
        )
    elif role == "psyche":
        body = (
            f"这个空间的心境偏{energy};被感知的在场感{occ},"
            f"亲疏带落在{deep}. 仿佛{simile}."
        )
    elif role == "soundscape":
        body = (
            f"在声场里,{energy}是前景事件,{occ}决定纹理的疏密,"
            f"{deep}是远近. 像在听{simile}."
        )
    else:
        body = f"以[{concept}]意象来看:能量{energy},密度{occ},方位{deep}."
    return f"{body}(隐喻解读·{name})"


def _build_analysis_steps(
    *,
    packet: EvidencePacket,
    role: str,
    entries: list[dict[str, Any]],
    primary: dict[str, Any],
    other: dict[str, Any],
    proposition: str,
) -> list[AnalysisStep]:
    """Visible reasoning trace: observe -> retrieve -> map -> reason -> conclude.

    Mirrors the auditable multi-step inference pattern (MiroFish-style):
    every claim carries the exact path from evidence scalars to metaphor.
    """
    signals = packet.signals
    signal_refs = [
        _ref(packet, "signals/motion/state"),
        _ref(packet, "signals/occupancy/state"),
        _ref(packet, "signals/depth/state"),
    ]
    quality_refs = [
        _ref(packet, "quality/overall_status"),
        _ref(packet, "quality/packet_coverage"),
    ]
    observe_text = (
        f"读取证据包标量: motion={signals.motion.state}, "
        f"occupancy={signals.occupancy_density.state}, "
        f"depth={signals.depth_zone.state}; 仅引用标量,未读取 raw CSI。"
    )
    retrieve_text = (
        f"从知识库命中主概念『{primary.get('concept', '空间')}』"
        f"({primary.get('source', '')}); 备用视角『{other.get('concept', '')}』。"
    )
    mappings = _signal_rules(entries, signals)
    map_text = (
        "; ".join(mappings)
        if mappings
        else "当前信号状态在知识库规则中无直接映射,按 persona 意象兜底。"
    )
    reason_text = _REASON_LINES.get(
        role,
        "隐喻映射成立的前提是标定与拓扑不变,且不改变任何数值。",
    )
    return [
        AnalysisStep(
            step_id="observe",
            phase="observe",
            title="观察信号",
            text=observe_text,
            evidence_refs=list(signal_refs),
        ),
        AnalysisStep(
            step_id="retrieve",
            phase="retrieve",
            title="检索知识库",
            text=retrieve_text,
            evidence_refs=list(quality_refs),
        ),
        AnalysisStep(
            step_id="map",
            phase="map",
            title="意象映射",
            text=map_text,
            evidence_refs=list(signal_refs),
        ),
        AnalysisStep(
            step_id="reason",
            phase="reason",
            title="推理",
            text=reason_text,
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


def _build_systematic_reading(
    *,
    packet: EvidencePacket,
    role: str,
    entries: list[dict[str, Any]],
    scene: dict[str, str],
    proposition: str,
) -> SystematicReading:
    """Structured persona-voiced interpretation of the full signal triplet."""
    readings = _signal_readings(entries, packet.signals)
    layers: list[ReadingLayer] = []
    explanations: list[str] = []
    for signal_name, state, metaphor in readings:
        scene_word = {
            "motion": scene["energy"],
            "occupancy": scene["occ"],
            "depth": scene["deep"],
        }[signal_name]
        explanation = _layer_explanation(
            role,
            signal_name,
            state,
            scene_word,
        )
        layers.append(
            ReadingLayer(
                signal=signal_name,
                state=state,
                metaphor=metaphor,
                explanation=explanation,
            )
        )
        explanations.append(explanation)
    opener = _NARRATIVE_OPENER.get(role, "综合三种标量:")
    closer = _NARRATIVE_CLOSER.get(role, "以上均为隐喻解读,不等于测量。")
    narrative = f"{opener} {' '.join(explanations)} {closer}"
    return SystematicReading(
        headline=proposition,
        scene_sketch=_SCENE_SKETCH.get(
            role,
            f"空间此刻呈现{scene['energy']}、{scene['occ']}、{scene['deep']}的整体气质。",
        ),
        layers=layers,
        narrative=narrative,
        boundary_notes=_BOUNDARY_NOTES.get(role, ["本解读为隐喻,不改变任何测量值。"]),
        multimodal_hints=_MULTIMODAL_HINTS.get(role, []),
    )


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
                update={"proposition": "此方位距离 3.2 米,大吉.(隐喻解读)"}
            )
        if self.misbehave_role == role:
            proposal = self._apply_misbehavior(packet, proposal)
        return self._cached(key, proposal)

    def _propose_themed(
        self,
        packet: EvidencePacket,
        role: AgentRole,
    ) -> SpecialistProposal:
        signals = packet.signals
        if signals.status in ("insufficient_signal", "uncalibrated"):
            return SpecialistProposal(
                abstain=True,
                kind="limitation",
                stance="neutral",
                proposition=(
                    f"信号 {signals.status};{role} 视角 abstain,"
                    "不做隐喻解读."
                ),
                evidence_refs=[
                    _ref(packet, "signals/motion/state"),
                    _ref(packet, "quality/overall_status"),
                ],
                falsification_test="不可证伪(abstain).",
                reasoning_summary="传感器明确 unavailable.",
            )
        knowledge = _load_knowledge(role)
        entries = knowledge.get("entries", [])
        if not entries:
            raise ValueError(f"knowledge base empty for {role}")
        index = _stable_index(packet, role)
        primary = entries[index % len(entries)]
        other = entries[(index + 1) % len(entries)]
        persona = knowledge.get("persona", {})
        scene = _scene_words(signals)
        proposition = _vivid_narrative(
            role,
            scene,
            index,
            persona,
            primary,
        )
        refs = [
            _ref(packet, "signals/motion/state"),
            _ref(packet, "signals/occupancy/state"),
            _ref(packet, "signals/depth/state"),
        ]
        if "rx-a" in packet.window_summary.links:
            refs.append(_ref(packet, "features/rx-a/temporal_diff_rms"))
        sources = [str(entry.get("url", "")) for entry in (primary, other)]
        steps = _build_analysis_steps(
            packet=packet,
            role=role,
            entries=entries,
            primary=primary,
            other=other,
            proposition=proposition,
        )
        systematic = _build_systematic_reading(
            packet=packet,
            role=role,
            entries=entries,
            scene=scene,
            proposition=proposition,
        )
        return SpecialistProposal(
            kind="observation",
            stance="supports",
            proposition=proposition,
            evidence_refs=refs,
            sources=[url for url in sources if url],
            process=(
                "数据路径: signals/motion|occupancy|depth -> 知识库概念映射 "
                "-> 意象合成;仅引用证据包标量,未读取 raw CSI."
            ),
            analysis_steps=steps,
            systematic_reading=systematic,
            assumptions=["标定 profile 与当前拓扑匹配", "隐喻解读不等于测量"],
            alternative_explanations=[
                f"另一视角:{other['concept']}",
                "无线干扰或结构变化也可能形成此意象",
            ],
            falsification_test=(
                "更换标定/拓扑或注入干扰后若意象不重现,则该隐喻解读不成立."
            ),
            reasoning_summary=(
                f"仅引用证据包标量;按知识库[{primary['concept']}]做隐喻映射."
            ),
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
                update={"proposition": "墙后有人,能看出一个人. "}
            )
        if self.misbehave == "fabricated_number":
            return proposal.model_copy(
                update={"proposition": "检测到运动,距离约 3.2 米. "}
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
            if self._claim_contradicts_sensor(packet, claim):
                challenges.append(
                    AgentChallengeOutput(
                        target_claim_id=claim.claim_id,
                        category="stale_evidence",
                        proposed_severity="blocking",
                        statement="主张叙述的意象与传感器 unknown 冲突;需要新证据.",
                        evidence_refs=[_ref(packet, "quality/overall_status")],
                        resolution_test="等待新的非 unknown 窗口后再评估.",
                    )
                )
            if not self._claim_is_labeled_metaphor(claim):
                challenges.append(
                    AgentChallengeOutput(
                        target_claim_id=claim.claim_id,
                        category="causal_overreach",
                        proposed_severity="blocking",
                        statement="隐喻解读未标注“(隐喻解读)”,易被误读为测量.",
                        evidence_refs=[_ref(packet, "quality/overall_status")],
                        resolution_test="补上隐喻标注并明确不改变任何数值.",
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
                    statement="干扰注入可能伪造“气动/流通/活动”意象,而非真实环境变化.",
                    evidence_refs=[
                        _ref(packet, "quality/packet_coverage"),
                        _ref(packet, "quality/overall_status"),
                    ],
                    resolution_test="对照无干扰注入的录制,若意象不重现则支持干扰假说.",
                )
            )
        if self.demo_scenario and packet.cycle_id == "cycle-0004" and non_abstain:
            challenges.append(
                AgentChallengeOutput(
                    target_claim_id=non_abstain[0].claim_id,
                    category="causal_overreach",
                    proposed_severity="blocking",
                    statement="演示注入的 blocking 挑战:该隐喻主张无法被当前证据解除.",
                    evidence_refs=[_ref(packet, "quality/packet_coverage")],
                    resolution_test="提供新的非 unknown 窗口证据.",
                )
            )
        if not challenges and non_abstain:
            challenges.append(
                AgentChallengeOutput(
                    target_claim_id=non_abstain[0].claim_id,
                    category="confound",
                    proposed_severity="info",
                    statement="环境静态变化(家具/门)也可能形成同样的空间意象.",
                    evidence_refs=[_ref(packet, "quality/packet_coverage")],
                    resolution_test="重放相同 bundle 并改变环境布置对比.",
                )
            )
        challenges = challenges[: self.config.max_challenges_total]
        return self._cached(key, ChallengeSet(challenges=challenges))

    @staticmethod
    def _claim_is_labeled_metaphor(claim: AgentClaim) -> bool:
        return "隐喻" in claim.proposition or "metaphor" in claim.proposition.lower()

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
        if approved.status == "unavailable":
            headline = "信号不可用,讨论受限"
            summary = "传感器信号 unavailable;不提供 presence 解读."
        elif approved.status == "ambiguous":
            headline = "证据解读存在未解决质疑"
            summary = (
                "存在未解决挑战:"
                + ", ".join(ch.challenge_id for ch in approved.challenges[:5])
                + "."
                if approved.challenges
                else "状态 ambiguous."
            )
        else:
            headline = "多视角受限解读"
            summary = " ".join(
                claim.proposition for claim in approved.claims[:3]
            ) or "无 accepted 主张."
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
                headline=headline,
                summary=summary,
                alternatives=list(dict.fromkeys(alternatives)),
                limitations=list(dict.fromkeys(limitations)),
                visual_parameters={"palette": "proxy_blue", "shape": "rings"},
                audio_parameters={"enabled": "false", "tone": "neutral"},
            ),
        )
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

    def _packet_prompt(self, packet: EvidencePacket) -> str:
        return (
            "当前 EvidencePacket(sealed,hash="
            f"{packet.evidence_hash}):\n{packet.model_dump_json()}"
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
        call = await self._run_structured(
            role=role,
            prompt=prompt,
            output_type=SpecialistProposal,
            user_input=self._packet_prompt(packet),
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

    async def challenge(
        self,
        packet: EvidencePacket,
        claims: list[AgentClaim],
        prompt: PromptVersion,
    ) -> ProviderCall[ChallengeSet]:
        key = self._cache_key("skeptic", "cross_examine", prompt, packet)
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
        call = await self._run_structured(
            role="fusion",
            prompt=prompt,
            output_type=SynthesisOutput,
            user_input=approved.model_dump_json(),
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
