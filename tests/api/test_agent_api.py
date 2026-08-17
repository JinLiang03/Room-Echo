"""Evaluator-friendly, read-only Agent response API."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from pathlib import Path

import httpx
import pytest
from wifi_api.app import app
from wifi_api.real_provider import reset_verified_runner_for_testing
from wifi_api.stream import StreamSession, reset_hub_for_testing
from wifi_contracts import ProviderHealth
from wifi_council.config import CouncilConfig
from wifi_council.provider import MockAgentProvider

ROOT = Path(__file__).resolve().parents[2]
BUNDLE = ROOT / "data" / "fixtures" / "walk_through"


class _TestOpenAIProvider(MockAgentProvider):
    """Deterministic test double with real-provider provenance."""

    name = "openai"

    def __init__(self, config: CouncilConfig) -> None:
        super().__init__(config)
        self.model = "test-openai-model"

    def health(self) -> ProviderHealth:
        return ProviderHealth(
            schema_version="provider-health.v1",
            provider="openai",
            status="ok",
            model=self.model,
            detail="configured test provider",
            checked_at=datetime.now(UTC),
        )


class _TestDeepSeekProvider(MockAgentProvider):
    """Deterministic double proving provider-neutral evaluator output."""

    name = "deepseek"

    def __init__(self, config: CouncilConfig) -> None:
        super().__init__(config)
        self.model = "test-deepseek-model"

    def health(self) -> ProviderHealth:
        return ProviderHealth(
            provider="deepseek",
            status="ok",
            model=self.model,
            detail="configured test provider",
            checked_at=datetime.now(UTC),
        )


def test_agent_latest_fails_honestly_without_a_session() -> None:
    reset_hub_for_testing()

    async def run() -> httpx.Response:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            return await client.get("/api/agent/latest")

    response = asyncio.run(run())
    assert response.status_code == 200
    payload = response.json()
    assert payload["schema_version"] == "agent-reading.v1"
    assert payload["status"] == "unavailable"
    assert payload["latest_triplet"] is None
    assert payload["council_cycle"] is None
    assert payload["real_model_calls"] == 0


def test_agent_query_returns_the_streams_audited_cycle_and_provenance(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PUBLIC_OPENAI_INVOKE", "1")
    reset_verified_runner_for_testing(_TestOpenAIProvider)
    hub = reset_hub_for_testing()
    session = StreamSession(bundle_root=BUNDLE, paced=False)
    hub.attach_session(session)

    async def run() -> tuple[httpx.Response, httpx.Response, httpx.Response]:
        session.start()
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/agent/query",
                json={"focus": "limitations", "wait_timeout_s": 15},
            )
            require_real = await client.post(
                "/api/agent/query",
                json={"wait_timeout_s": 0, "require_openai": True},
            )
            invoke = await client.post(
                "/api/agent/invoke",
                json={"focus": "overview", "evidence_wait_timeout_s": 15},
            )
        await session.stop()
        return response, require_real, invoke

    try:
        response, require_real, invoke = asyncio.run(run())
        assert response.status_code == 200
        payload = response.json()
        assert payload["session_id"] == session.session_id
        assert payload["source_mode"] == "replay"
        assert payload["focus"] == "limitations"
        assert payload["provider"] == "mock"
        assert payload["real_model_calls"] == 0
        assert payload["latest_triplet"]["session_id"] == session.session_id
        assert payload["council_cycle"]["cycle_id"]
        assert payload["council_cycle"]["result"] is not None
        assert payload["cycle_status"] == payload["council_cycle"]["status"]
        assert payload["usage"]["cycles_completed"] >= 1
        assert payload["response_latency_ms"] >= 0
        assert any("not a camera" in item for item in payload["truth_boundary"])
        assert require_real.status_code == 503
        assert "mock output is never presented" in require_real.json()["detail"]
        assert invoke.status_code == 200
        invoke_payload = invoke.json()
        assert invoke_payload["status"] == "ready"
        assert invoke_payload["cycle_status"] == invoke_payload["council_cycle"]["status"]
        assert invoke_payload["council_cycle"] is not None
        assert invoke_payload["provider"] == "openai"
        assert invoke_payload["real_model_calls"] >= 7
        phases = {
            call["phase"] for call in invoke_payload["council_cycle"]["calls"]
        }
        assert {"propose", "cross_examine", "synthesize"} <= phases
    finally:
        reset_verified_runner_for_testing()
        reset_hub_for_testing()


def test_agent_invoke_reports_deepseek_and_only_network_equivalent_calls(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PUBLIC_REAL_PROVIDER_INVOKE", "1")
    reset_verified_runner_for_testing(_TestDeepSeekProvider)
    hub = reset_hub_for_testing()
    session = StreamSession(bundle_root=BUNDLE, paced=False)
    hub.attach_session(session)

    async def run() -> httpx.Response:
        session.start()
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://test",
        ) as client:
            response = await client.post(
                "/api/agent/invoke",
                json={"focus": "overview", "evidence_wait_timeout_s": 15},
            )
        await session.stop()
        return response

    try:
        response = asyncio.run(run())
        assert response.status_code == 200
        payload = response.json()
        assert payload["status"] == "ready"
        assert payload["cycle_status"] == payload["council_cycle"]["status"]
        assert payload["provider"] == "deepseek"
        assert payload["provider_health"]["model"] == "test-deepseek-model"
        assert payload["real_model_calls"] >= 7
        assert all(
            call["status"] == "ok"
            for call in payload["council_cycle"]["calls"]
            if call["status"] != "cache_hit"
        )
    finally:
        reset_verified_runner_for_testing()
        reset_hub_for_testing()
