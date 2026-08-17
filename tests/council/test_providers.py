"""Provider behaviors: mock determinism, caching, OpenAI health/smoke."""

from __future__ import annotations

import asyncio
import json
import os
from types import SimpleNamespace
from typing import Any, cast

import pytest
from _helpers import make_packet
from wifi_council.config import CouncilConfig
from wifi_council.deepseek import DeepSeekAgentProvider
from wifi_council.orchestrator import CouncilOrchestrator
from wifi_council.outputs import ApprovedCouncilInput, ProxyMeasurementSummary
from wifi_council.prompts import build_prompt, prompt_registry
from wifi_council.provider import MockAgentProvider, OpenAIAgentProvider


def test_mock_is_deterministic_across_instances() -> None:
    packet = make_packet()
    first = MockAgentProvider(CouncilConfig())
    second = MockAgentProvider(CouncilConfig())

    async def run(provider):
        call = await provider.propose("feng_shui", packet, build_prompt("feng_shui"))
        assert call.value is not None
        return call.value.model_dump(mode="json")

    assert asyncio.run(run(first)) == asyncio.run(run(second))


def test_mock_proposal_carries_full_analysis_trace() -> None:
    packet = make_packet()
    provider = MockAgentProvider(CouncilConfig())

    async def run():
        call = await provider.propose("feng_shui", packet, build_prompt("feng_shui"))
        assert call.value is not None
        return call.value

    proposal = asyncio.run(run())
    phases = [step.phase for step in proposal.analysis_steps]
    assert phases == ["observe", "retrieve", "map", "reason", "conclude"]
    assert all(step.title for step in proposal.analysis_steps)
    assert all(step.text for step in proposal.analysis_steps)
    assert proposal.analysis_steps[0].evidence_refs
    assert "quality=ok" in proposal.analysis_steps[0].text
    assert "sealed 代理字段" in proposal.analysis_steps[0].text
    # 每个主题角色都应得到同样的轨迹结构
    for role in ("architecture", "biota", "psyche", "soundscape"):
        call = asyncio.run(
            provider.propose(role, packet, build_prompt(role))
        )
        assert call.value is not None
        assert [step.phase for step in call.value.analysis_steps] == phases


def test_mock_proposal_carries_systematic_reading() -> None:
    packet = make_packet()
    provider = MockAgentProvider(CouncilConfig())

    async def run():
        call = await provider.propose("feng_shui", packet, build_prompt("feng_shui"))
        assert call.value is not None
        return call.value

    proposal = asyncio.run(run())
    reading = proposal.systematic_reading
    assert reading is not None
    assert reading.headline == proposal.render_proposition()
    assert len(reading.layers) == 3
    assert [layer.signal for layer in reading.layers] == [
        "motion",
        "occupancy",
        "depth",
    ]
    assert all(layer.metaphor for layer in reading.layers)
    assert all(layer.explanation for layer in reading.layers)
    assert reading.scene_sketch
    assert reading.narrative
    assert reading.boundary_notes
    assert reading.multimodal_hints


def test_all_specialists_share_current_j_context_but_keep_distinct_lenses() -> None:
    packet = make_packet()
    provider = MockAgentProvider(CouncilConfig())
    roles = ("architecture", "biota", "feng_shui", "psyche", "soundscape")
    proposals = []
    for role in roles:
        call = asyncio.run(provider.propose(role, packet, build_prompt(role)))
        assert call.value is not None
        proposals.append(call.value)

    assert len({proposal.scene_question for proposal in proposals}) == 1
    assert all(
        proposal.measurement_summary == ProxyMeasurementSummary.from_packet(packet)
        for proposal in proposals
    )
    assert len({proposal.lens_focus for proposal in proposals}) == len(roles)
    assert len({proposal.plain_language for proposal in proposals}) == len(roles)
    required_paths = {
        "signals/motion/state",
        "signals/occupancy/state",
        "signals/depth/state",
        "quality/overall_status",
    }
    for proposal in proposals:
        refs = {
            path
            for path in required_paths
            if any(ref.endswith(f"/{path}") for ref in proposal.evidence_refs)
        }
        assert refs == required_paths
        rendered = proposal.render_proposition()
        assert "活动=moving" in rendered
        assert "占用=low" in rendered
        assert "相对纵深=near" in rendered
        assert "质量=ok" in rendered
        assert "空间生命体反应(叙事隐喻,不表示真实生命或意识)" in rendered
        assert "限制:" in rendered


def test_reaction_changes_with_the_current_proxy_snapshot() -> None:
    provider = MockAgentProvider(CouncilConfig())
    calm = make_packet(
        cycle_id="cycle-calm",
        motion_state="idle",
        occupancy_state="low",
        depth_state="near",
    )
    active = make_packet(
        cycle_id="cycle-active",
        motion_state="fast_change",
        occupancy_state="high",
        depth_state="far",
    )

    calm_call = asyncio.run(
        provider.propose("architecture", calm, build_prompt("architecture"))
    )
    active_call = asyncio.run(
        provider.propose("architecture", active, build_prompt("architecture"))
    )
    assert calm_call.value is not None and active_call.value is not None
    assert calm_call.value.reaction.model_dump() == {
        "motion": "安静",
        "occupancy": "舒展",
        "depth": "靠近",
    }
    assert active_call.value.reaction.model_dump() == {
        "motion": "躁动",
        "occupancy": "收紧",
        "depth": "退后",
    }
    assert calm_call.value.render_proposition() != active_call.value.render_proposition()


def test_provider_independent_validation_rejects_stale_measurement_summary() -> None:
    packet = make_packet()
    provider = MockAgentProvider(CouncilConfig())
    call = asyncio.run(
        provider.propose("architecture", packet, build_prompt("architecture"))
    )
    assert call.value is not None
    stale = call.value.model_copy(
        update={
            "measurement_summary": call.value.measurement_summary.model_copy(
                update={"motion": "idle"}
            )
        }
    )
    with pytest.raises(ValueError, match="current EvidencePacket"):
        stale.validate_for(packet, "architecture")


def test_mock_cache_returns_cache_hit() -> None:
    provider = MockAgentProvider(CouncilConfig())
    packet = make_packet()

    async def run():
        await provider.propose("feng_shui", packet, build_prompt("feng_shui"))
        second = await provider.propose("feng_shui", packet, build_prompt("feng_shui"))
        return second

    call = asyncio.run(run())
    assert call.status == "cache_hit"
    assert call.cache_hit is True


def test_cache_never_crosses_prompt_version() -> None:
    provider = MockAgentProvider(CouncilConfig())
    packet = make_packet()

    async def run():
        await provider.propose(
            "feng_shui", packet, build_prompt("feng_shui", "council-prompt.v1")
        )
        second = await provider.propose(
            "feng_shui",
            packet,
            build_prompt("feng_shui", "council-prompt.v2"),
        )
        return second

    call = asyncio.run(run())
    assert call.status == "ok"
    assert call.cache_hit is False


def test_prompt_registry_is_versioned_and_stable() -> None:
    registry = prompt_registry()
    assert set(registry) == {
        "architecture",
        "biota",
        "feng_shui",
        "psyche",
        "soundscape",
        "skeptic",
        "fusion",
    }
    for role, prompt in registry.items():
        assert prompt.version == "council-prompt.v3"
        assert prompt.sha256.startswith("sha256:")
        assert prompt.sha256 == build_prompt(role).sha256
        assert "不得推断身份" in prompt.text
    again = prompt_registry()
    assert {role: prompt.sha256 for role, prompt in registry.items()} == {
        role: prompt.sha256 for role, prompt in again.items()
    }


def test_openai_without_key_is_offline_and_never_leaks_key() -> None:
    config = CouncilConfig()
    provider = OpenAIAgentProvider(config, api_key=None)
    health = provider.health()
    assert health.status == "degraded"
    assert "API key" in health.detail
    assert "sk-" not in health.model_dump_json()

    async def propose():
        return await provider.propose(
            "feng_shui", make_packet(), build_prompt("feng_shui")
        )

    call = asyncio.run(propose())
    assert call.status == "offline"
    assert call.value is None


def test_deepseek_without_key_is_offline_and_never_leaks_key() -> None:
    provider = DeepSeekAgentProvider(CouncilConfig(), api_key="")
    health = provider.health()
    assert health.provider == "deepseek"
    assert health.status == "degraded"
    assert "DeepSeek API key" in health.detail
    assert "sk-" not in health.model_dump_json()

    call = asyncio.run(
        provider.propose(
            "architecture",
            make_packet(),
            build_prompt("architecture"),
        )
    )
    assert call.status == "offline"
    assert call.value is None


def test_deepseek_json_output_is_schema_bound_and_audited() -> None:
    packet = make_packet()
    narrative = {
        "plain_language": "该视角把当前代理组合读作可对照的空间节奏(叙事隐喻)",
        "uncertainty": "静态布置或无线干扰仍可能形成相似组合",
        "alternative_explanations": ["布置变化", "无线干扰"],
        "falsification_test": "保持拓扑不变并对照下一周期",
        "reasoning_summary": "只解释当前封存快照",
    }
    completions = _FakeDeepSeekCompletions(
        json.dumps(narrative, ensure_ascii=False)
    )
    provider = DeepSeekAgentProvider(
        CouncilConfig(),
        api_key="test-only-key",
        model="deepseek-test",
        base_url="https://example.invalid",
    )
    provider._client = cast(Any, SimpleNamespace(chat=SimpleNamespace(completions=completions)))

    async def run():
        first = await provider.propose(
            "architecture", packet, build_prompt("architecture")
        )
        second = await provider.propose(
            "architecture", packet, build_prompt("architecture")
        )
        return first, second

    call, cached = asyncio.run(run())
    assert call.status == "ok"
    assert call.value is not None
    assert call.value.plain_language == narrative["plain_language"]
    assert call.value.measurement_summary == ProxyMeasurementSummary.from_packet(packet)
    assert call.value.lens_focus == "spatial_flow"
    assert call.value.analysis_steps
    assert call.value.systematic_reading is not None
    assert all(ref.startswith(f"evidence://{packet.evidence_hash}/") for ref in call.value.evidence_refs)
    assert call.model == "deepseek-test"
    assert call.trace_id == "deepseek-test-response"
    assert call.input_tokens == 101
    assert call.output_tokens == 37
    assert completions.kwargs["response_format"] == {"type": "json_object"}
    assert completions.kwargs["extra_body"] == {"thinking": {"type": "disabled"}}
    assert '"raw_ref":' not in completions.kwargs["messages"][1]["content"]
    assert "均由服务器根据 sealed packet 回填" in completions.kwargs["messages"][0]["content"]
    assert cached.status == "cache_hit"
    assert cached.cache_hit is True
    assert completions.calls == 1
    assert "test-only-key" not in repr(call)


def test_deepseek_skeptic_rebinds_target_and_refs_to_current_cycle() -> None:
    packet = make_packet()
    mock = MockAgentProvider(CouncilConfig())
    detail = asyncio.run(CouncilOrchestrator(mock, CouncilConfig()).run_cycle(packet))
    assert detail.claims
    claims = detail.claims[:1]
    content = json.dumps(
        {
            "challenges": [
                {
                    "target_claim_id": "claim-outside-current-cycle",
                    "category": "confound",
                    "proposed_severity": "material",
                    "statement": "当前角色读法仍有替代解释",
                    "resolution_test": "对照下一周期是否延续",
                }
            ]
        },
        ensure_ascii=False,
    )
    completions = _FakeDeepSeekCompletions(content)
    provider = DeepSeekAgentProvider(
        CouncilConfig(),
        api_key="test-only-key",
        model="deepseek-test",
        base_url="https://example.invalid",
    )
    provider._client = cast(
        Any,
        SimpleNamespace(chat=SimpleNamespace(completions=completions)),
    )

    call = asyncio.run(
        provider.challenge(packet, claims, build_prompt("skeptic"))
    )
    assert call.status == "ok"
    assert call.value is not None
    assert len(call.value.challenges) == 1
    challenge = call.value.challenges[0]
    assert challenge.target_claim_id == claims[0].claim_id
    assert challenge.evidence_refs
    assert all(
        ref.startswith(f"evidence://{packet.evidence_hash}/")
        for ref in challenge.evidence_refs
    )


def test_deepseek_fusion_cannot_write_measurements_or_visual_parameters() -> None:
    packet = make_packet()
    approved = ApprovedCouncilInput(
        packet=packet,
        claims=[],
        challenges=[],
        status="supported",
        sensor_confidence_cap=packet.signals.sensor_confidence_cap,
        model_support=0.0,
        display_confidence=0.0,
    )
    content = json.dumps(
        {
            "headline": "本轮可作为对照候选",
            "plain_language": "五个视角围绕同一代理快照给出受限解释",
            "action": "保存并与下一周期对照",
            "uncertainty": "静态布置与无线干扰仍是替代解释",
            "alternatives": ["静态布置变化"],
            "limitations": ["代理信号不是影像"],
        },
        ensure_ascii=False,
    )
    completions = _FakeDeepSeekCompletions(content)
    provider = DeepSeekAgentProvider(
        CouncilConfig(),
        api_key="test-only-key",
        model="deepseek-test",
        base_url="https://example.invalid",
    )
    provider._client = cast(
        Any,
        SimpleNamespace(chat=SimpleNamespace(completions=completions)),
    )

    call = asyncio.run(provider.synthesize(approved, build_prompt("fusion")))
    assert call.status == "ok"
    assert call.value is not None
    assert call.value.measurement_summary == ProxyMeasurementSummary.from_packet(packet)
    assert call.value.visual_parameters == {}
    assert call.value.audio_parameters == {}
    assert "由服务器回填" in completions.kwargs["messages"][0]["content"]


def test_deepseek_grounded_outputs_complete_full_council_path() -> None:
    packet = make_packet()
    completions = _RoutingDeepSeekCompletions()
    provider = DeepSeekAgentProvider(
        CouncilConfig(max_calls_per_cycle=10),
        api_key="test-only-key",
        model="deepseek-test",
        base_url="https://example.invalid",
    )
    provider._client = cast(
        Any,
        SimpleNamespace(chat=SimpleNamespace(completions=completions)),
    )

    detail = asyncio.run(
        CouncilOrchestrator(
            provider,
            CouncilConfig(max_calls_per_cycle=10),
        ).run_cycle(packet)
    )
    successful = [record for record in detail.calls if record.status == "ok"]
    assert detail.result is not None
    assert len(successful) >= 7
    assert {record.phase for record in successful} >= {
        "propose",
        "cross_examine",
        "synthesize",
    }
    assert len(detail.claims) == 5
    assert completions.calls == len(successful)
    assert detail.result.display_confidence <= detail.result.sensor_confidence_cap


class _FakeDeepSeekCompletions:
    def __init__(self, content: str) -> None:
        self.content = content
        self.kwargs: dict[str, Any] = {}
        self.calls = 0

    async def create(self, **kwargs: Any) -> Any:
        self.calls += 1
        self.kwargs = kwargs
        return SimpleNamespace(
            id="deepseek-test-response",
            choices=[
                SimpleNamespace(
                    finish_reason="stop",
                    message=SimpleNamespace(content=self.content),
                )
            ],
            usage=SimpleNamespace(prompt_tokens=101, completion_tokens=37),
        )


class _RoutingDeepSeekCompletions:
    """Return a minimal valid narrative for each DeepSeek output schema."""

    def __init__(self) -> None:
        self.calls = 0

    async def create(self, **kwargs: Any) -> Any:
        self.calls += 1
        system = str(kwargs["messages"][0]["content"])
        if '"title":"DeepSeekProposalNarrative"' in system:
            payload = {
                "plain_language": "该角色把当前组合读作可对照的节奏(叙事隐喻)",
                "uncertainty": "静态布置和无线干扰仍可能形成相似组合",
                "alternative_explanations": ["静态布置变化"],
                "falsification_test": "保持拓扑不变并对照下一周期",
                "reasoning_summary": "只解释当前封存快照",
            }
        elif '"title":"DeepSeekChallengeNarratives"' in system:
            payload = {"challenges": []}
        elif '"title":"ResponseOutput"' in system:
            payload = {
                "state": "conceded",
                "reasoning_summary": "接受替代解释并等待下一周期",
            }
        elif '"title":"DeepSeekSynthesisNarrative"' in system:
            payload = {
                "headline": "本轮可作为对照候选",
                "plain_language": "多个受限视角解释了同一封存代理快照",
                "action": "保存并与下一周期对照",
                "uncertainty": "代理量不是影像或米制距离",
                "alternatives": ["无线干扰"],
                "limitations": ["只适用于当前标定与拓扑"],
            }
        else:  # pragma: no cover - makes an unexpected schema fail loudly
            raise AssertionError("unexpected DeepSeek schema")
        return SimpleNamespace(
            id=f"deepseek-routing-{self.calls}",
            choices=[
                SimpleNamespace(
                    finish_reason="stop",
                    message=SimpleNamespace(
                        content=json.dumps(payload, ensure_ascii=False)
                    ),
                )
            ],
            usage=SimpleNamespace(prompt_tokens=101, completion_tokens=37),
        )


@pytest.mark.openai_smoke
@pytest.mark.skipif(
    not os.environ.get("COUNCIL_OPENAI_SMOKE"),
    reason="opt-in OpenAI integration smoke; set COUNCIL_OPENAI_SMOKE=1 and a server-side key",
)
def test_openai_provider_smoke() -> None:
    """Opt-in: records model/latency/status/usage; never logs the key."""
    config = CouncilConfig()
    provider = OpenAIAgentProvider(config)
    if not provider.api_key:
        pytest.skip("no OPENAI_API_KEY in server environment")

    async def run():
        return await provider.propose(
            "feng_shui", make_packet(), build_prompt("feng_shui")
        )

    call = asyncio.run(run())
    assert call.status == "ok"
    assert call.value is not None
    assert call.model == provider.model
    assert call.latency_ms >= 0
    assert call.input_tokens + call.output_tokens >= 0
    assert "sk-" not in repr(call)


@pytest.mark.deepseek_smoke
@pytest.mark.skipif(
    not os.environ.get("COUNCIL_DEEPSEEK_SMOKE"),
    reason="opt-in DeepSeek integration smoke; set COUNCIL_DEEPSEEK_SMOKE=1",
)
def test_deepseek_provider_smoke() -> None:
    provider = DeepSeekAgentProvider(CouncilConfig())
    if not provider.api_key:
        pytest.skip("no DEEPSEEK_API_KEY in server environment")

    call = asyncio.run(
        provider.propose(
            "architecture",
            make_packet(),
            build_prompt("architecture"),
        )
    )
    assert call.status == "ok"
    assert call.value is not None
    assert call.model == provider.model
    assert call.trace_id
    assert call.input_tokens > 0
    assert call.output_tokens > 0
