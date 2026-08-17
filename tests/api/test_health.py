"""Smoke tests for the /healthz endpoint."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from wifi_api.app import app
from wifi_api.config import get_app_mode
from wifi_api.stream import StreamSession, reset_hub_for_testing

client = TestClient(app)


def test_healthz_returns_version_mode_and_components() -> None:
    response = client.get("/healthz")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["service"] == "wifi-spatial-council-api"
    assert payload["version"] == "0.1.0"
    assert payload["mode"] in {"mock", "replay", "live"}
    assert payload["contracts_version"] == "1.0.0"
    assert "api" in payload["components"]
    assert "contracts" in payload["components"]
    assert payload["components"]["collector"]["status"] == "ok"
    assert payload["components"]["sensing"]["status"] == "ok"
    assert "not_implemented" not in response.text


def test_healthz_does_not_leak_env_values_or_absolute_paths() -> None:
    body = client.get("/healthz").text
    for secret_name in ("OPENAI_API_KEY", "RX_A_PORT", "SERIAL_BAUD"):
        assert secret_name not in body
    assert "/Users" not in body
    assert "http://" not in body


def test_app_mode_reads_valid_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_MODE", "replay")
    assert get_app_mode() == "replay"


def test_app_mode_rejects_unknown_value(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_MODE", "camera")
    with pytest.raises(ValueError, match="APP_MODE"):
        get_app_mode()


def test_healthz_reflects_runtime_source_degradation() -> None:
    hub = reset_hub_for_testing()
    bundle = Path(__file__).resolve().parents[2] / "data" / "fixtures" / "walk_through"
    session = StreamSession(bundle_root=bundle, paced=False)
    hub.attach_session(session)
    hub.publish(
        session.session_id,
        "source.health",
        {"status": "degraded"},
    )
    try:
        response = client.get("/healthz")
        assert response.status_code == 200
        payload = response.json()
        assert payload["status"] == "degraded"
        assert payload["components"]["collector"]["status"] == "degraded"
        assert payload["components"]["sensing"]["status"] == "degraded"
    finally:
        reset_hub_for_testing()
