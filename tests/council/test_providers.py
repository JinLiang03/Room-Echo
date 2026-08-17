"""Provider behaviors: mock determinism, caching, OpenAI health/smoke."""

from __future__ import annotations

import asyncio
import os

import pytest
from _helpers import make_packet
from wifi_council.config import CouncilConfig
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
    assert "raw CSI" in proposal.analysis_steps[0].text
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
    assert reading.headline == proposal.proposition
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
        assert prompt.version == "council-prompt.v1"
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
