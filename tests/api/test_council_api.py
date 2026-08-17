"""Council API routes: health, usage, cycle detail, rejections."""

from __future__ import annotations

from fastapi.testclient import TestClient
from wifi_api.app import app

client = TestClient(app)


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
