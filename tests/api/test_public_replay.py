"""Fail-closed public Replay mode and same-origin Web serving."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from wifi_api import app as app_module
from wifi_api.app import app, mount_web_assets
from wifi_api.config import PUBLIC_REPLAY_BUNDLE_ID, public_replay, serve_web
from wifi_api.stream import reset_hub_for_testing

client = TestClient(app)
ROOT = Path(__file__).resolve().parents[2]


def test_public_replay_flags_are_exact_opt_ins(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("PUBLIC_REPLAY", raising=False)
    monkeypatch.delenv("SERVE_WEB", raising=False)
    assert public_replay() is False
    assert serve_web() is False

    monkeypatch.setenv("PUBLIC_REPLAY", "true")
    monkeypatch.setenv("SERVE_WEB", "yes")
    assert public_replay() is False
    assert serve_web() is False

    monkeypatch.setenv("PUBLIC_REPLAY", "1")
    monkeypatch.setenv("SERVE_WEB", "1")
    assert public_replay() is True
    assert serve_web() is True


def test_public_replay_forces_supervised_demo_configuration(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PUBLIC_REPLAY", "1")
    monkeypatch.setenv("APP_MODE", "live")
    monkeypatch.setenv("SCENARIO", "walk_through")
    monkeypatch.setenv("DEMO_AUTOSTART", "0")
    monkeypatch.setenv("DEMO_LOOP", "0")

    assert app_module._demo_boot_config() == (
        True,
        "replay",
        PUBLIC_REPLAY_BUNDLE_ID,
        True,
    )


def test_public_replay_loop_does_not_create_unbounded_event_logs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PUBLIC_REPLAY", "1")

    session = app_module._build_demo_session("replay", PUBLIC_REPLAY_BUNDLE_ID)

    assert session._event_log_path is None


@pytest.mark.parametrize(
    ("path", "kwargs"),
    [
        ("/api/stream/start", {"params": {"bundle_id": "demo_2min"}}),
        ("/api/stream/start", {"params": {"mode": "mock", "scenario": "idle"}}),
        ("/api/stream/start", {"params": {"mode": "live"}}),
        ("/api/stream/control", {"json": {"action": "pause"}}),
        ("/api/stream/control", {"json": {"action": "resume"}}),
        ("/api/stream/control", {"json": {"action": "step", "frames": 1}}),
        ("/api/stream/control", {"json": {"action": "seek", "seconds": 1}}),
        ("/api/stream/control", {"json": {"action": "rate", "rate": 2}}),
        ("/api/stream/control", {"json": {"action": "record"}}),
        ("/api/stream/control", {"json": {"action": "start"}}),
        ("/api/stream/control", {"json": {"action": "stop"}}),
        ("/api/stream/stop", {}),
        ("/api/stream/faults/packet_loss", {"json": {"active": True}}),
    ],
)
def test_public_replay_rejects_every_anonymous_mutation(
    monkeypatch: pytest.MonkeyPatch,
    path: str,
    kwargs: dict[str, object],
) -> None:
    monkeypatch.setenv("PUBLIC_REPLAY", "1")
    reset_hub_for_testing()
    try:
        response = client.post(path, **kwargs)  # type: ignore[arg-type]
        assert response.status_code == 403
        assert "read-only" in response.json()["detail"]
    finally:
        reset_hub_for_testing()


def test_public_replay_exposes_only_the_sealed_demo_bundle(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PUBLIC_REPLAY", "1")
    response = client.get("/api/replay/bundles")
    assert response.status_code == 200
    assert [item["bundle_id"] for item in response.json()] == [
        PUBLIC_REPLAY_BUNDLE_ID
    ]
    assert client.get("/api/replay/bundles/walk_through").status_code == 404


def test_public_websocket_keeps_hello_and_ping_but_rejects_control(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PUBLIC_REPLAY", "1")
    reset_hub_for_testing()
    try:
        with client.websocket_connect("/ws") as websocket:
            assert websocket.receive_json()["event_type"] == "snapshot"

            websocket.send_json({"type": "ping"})
            assert websocket.receive_json() == {"type": "pong"}

            websocket.send_json({"type": "hello", "last_sequence": 0})
            assert websocket.receive_json()["event_type"] == "snapshot"

            websocket.send_json({"type": "control", "action": "pause"})
            rejected = websocket.receive_json()
            assert rejected["status"] == 403
            assert "read-only" in rejected["detail"]
    finally:
        reset_hub_for_testing()


def test_mount_web_assets_preserves_api_precedence_and_serves_index(
    tmp_path: Path,
) -> None:
    dist = tmp_path / "dist"
    assets = dist / "assets"
    assets.mkdir(parents=True)
    (dist / "index.html").write_text(
        "<!doctype html><title>competition replay</title>",
        encoding="utf-8",
    )
    (assets / "app.js").write_text("export const ready = true;", encoding="utf-8")

    isolated = FastAPI()

    @isolated.get("/healthz")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    mount_web_assets(isolated, dist)
    isolated_client = TestClient(isolated)

    assert isolated_client.get("/healthz").json() == {"status": "ok"}
    assert "competition replay" in isolated_client.get("/").text
    assert "ready = true" in isolated_client.get("/assets/app.js").text


def test_mount_web_assets_fails_clearly_without_a_build(tmp_path: Path) -> None:
    with pytest.raises(RuntimeError, match=r"SERVE_WEB=1.*npm --prefix"):
        mount_web_assets(FastAPI(), tmp_path / "missing-dist")


def test_deployment_artifacts_keep_the_loop_single_worker_and_cost_bounded() -> None:
    dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")
    blueprint = (ROOT / "render.yaml").read_text(encoding="utf-8")
    dockerignore = (ROOT / ".dockerignore").read_text(encoding="utf-8")

    assert "--workers 1" in dockerfile
    assert "USER appuser" in dockerfile
    assert "PUBLIC_REPLAY=1" in dockerfile
    assert "value: mock" in blueprint
    assert "key: PUBLIC_REAL_PROVIDER_INVOKE" in blueprint
    assert "key: REAL_AGENT_PROVIDER" in blueprint
    assert "value: deepseek" in blueprint
    assert "key: DEEPSEEK_API_KEY" in blueprint
    assert "sync: false" in blueprint
    assert "DEEPSEEK_API_KEY\n        value:" not in blueprint
    assert ".env" in dockerignore
