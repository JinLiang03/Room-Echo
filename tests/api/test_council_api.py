"""Council API routes: health, usage, cycle detail, rejections."""

from __future__ import annotations

import asyncio
from pathlib import Path

from fastapi.testclient import TestClient
from wifi_api import council_routes
from wifi_api.app import app
from wifi_api.stream import StreamSession, reset_hub_for_testing
from wifi_council.runtime import CouncilRuntime

client = TestClient(app)
ROOT = Path(__file__).resolve().parents[2]
WALK_THROUGH = ROOT / "data" / "fixtures" / "walk_through"


def test_council_health_reports_providers_without_secrets() -> None:
    response = client.get("/council/health")
    assert response.status_code == 200
    payload = response.json()
    assert len(payload) >= 2
    providers = {entry["provider"] for entry in payload}
    assert {"mock", "openai"} <= providers
    assert "sk-" not in response.text
    assert "OPENAI_API_KEY" not in response.text


def test_council_usage_returns_summary() -> None:
    response = client.get("/council/usage")
    assert response.status_code == 200
    payload = response.json()
    assert payload["schema_version"] == "council-usage.v1"
    assert payload["cycles_completed"] >= 0


def test_council_cycles_empty_and_unknown_cycle_404() -> None:
    response = client.get("/council/cycles")
    assert response.status_code == 200
    assert isinstance(response.json(), list)
    missing = client.get("/council/cycles/cycle-does-not-exist")
    assert missing.status_code == 404


def test_council_endpoints_never_expose_keys_or_paths() -> None:
    for path in ("/council/health", "/council/usage", "/council/cycles"):
        body = client.get(path).text
        assert "OPENAI_API_KEY" not in body
        assert "/Users" not in body


def test_streamed_council_cycles_are_visible_through_rest(
    monkeypatch,
    tmp_path: Path,
) -> None:
    """REST must expose the same store whose cycles were sent over the stream."""
    hub = reset_hub_for_testing()
    fallback = CouncilRuntime()
    monkeypatch.setattr(council_routes, "get_runtime", lambda: fallback)
    session = StreamSession(
        bundle_root=WALK_THROUGH,
        paced=False,
        event_log_dir=tmp_path,
    )
    hub.attach_session(session)

    async def run() -> None:
        session.start()
        deadline = asyncio.get_running_loop().time() + 60.0
        while not session.status()["finished"] and not session.status()["error"]:
            if asyncio.get_running_loop().time() > deadline:
                raise AssertionError(f"session did not finish: {session.status()}")
            await asyncio.sleep(0.01)

    try:
        asyncio.run(run())
        streamed_cycles = {
            event["payload"]["cycle_id"]
            for event in hub._buffer
            if event["event_type"] == "agent.claim"
        }
        runtime = session.council_runtime
        assert streamed_cycles
        assert runtime is not None
        assert runtime is not fallback

        cycles = client.get("/council/cycles")
        assert cycles.status_code == 200
        assert streamed_cycles <= set(cycles.json())

        usage = client.get("/council/usage")
        assert usage.status_code == 200
        assert usage.json()["cycles_completed"] == len(runtime.store.cycle_ids())
        assert usage.json()["cycles_completed"] >= len(streamed_cycles)

        cycle_id = next(iter(streamed_cycles))
        detail = client.get(f"/council/cycles/{cycle_id}")
        assert detail.status_code == 200
        assert detail.json()["cycle_id"] == cycle_id
    finally:
        reset_hub_for_testing()
