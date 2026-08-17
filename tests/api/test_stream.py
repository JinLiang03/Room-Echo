"""Realtime stream: events, sequences, snapshot recovery, controls, REST."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient
from wifi_api.app import app
from wifi_api.replay_routes import StreamStatus
from wifi_api.stream import (
    BUFFER_LIMIT,
    CalibrationUnavailableError,
    StreamHub,
    StreamSession,
    _load_profile,
    get_hub,
    reset_hub_for_testing,
)
from wifi_collector.replay_bundle import BundleVerifier
from wifi_sensing.calibration import CalibrationMetrics, CalibrationProfile, demo_profile
from wifi_sensing.config import FeatureConfig

ROOT = Path(__file__).resolve().parents[2]
BUNDLE = ROOT / "data" / "fixtures" / "walk_through"

client = TestClient(app)
TEST_TOPOLOGY_HASH = "sha256:" + "a" * 64


def _write_live_profile(path: Path) -> CalibrationProfile:
    seed = demo_profile(FeatureConfig(), TEST_TOPOLOGY_HASH)
    values = seed.model_dump(exclude={"checksum"})
    values.update(
        {
            "profile_id": "live-room-v1",
            "source": "recorded",
            "simulated": False,
            "fitted_at": datetime.now(UTC),
            "board_hashes": {
                "tx": "sha256:" + "1" * 64,
                "rx-a": "sha256:" + "2" * 64,
                "rx-b": "sha256:" + "3" * 64,
            },
            "metrics": CalibrationMetrics(
                motion_separation=0.8,
                occupancy_ordinal_accuracy=0.8,
                depth_monotonic_accuracy=0.8,
                held_out_trial_ids=["held-out-1"],
                evaluated_at=datetime.now(UTC),
                simulated=False,
            ),
        }
    )
    profile = CalibrationProfile.create(**values)
    path.write_text(profile.model_dump_json(indent=2), encoding="utf-8")
    return profile


async def _run_session(hub: StreamHub, paced: bool = False) -> StreamSession:
    session = StreamSession(bundle_root=BUNDLE, paced=paced, rate=2.0)
    hub.attach_session(session)
    session.start()
    deadline = asyncio.get_event_loop().time() + 60.0
    while not session.status()["finished"] and not session.status()["error"]:
        if asyncio.get_event_loop().time() > deadline:
            raise AssertionError("session did not finish")
        await asyncio.sleep(0.02)
    return session


def test_session_emits_monotonic_stream_events() -> None:
    hub = StreamHub()

    async def run() -> tuple[StreamSession, list[dict]]:
        session = await _run_session(hub)
        return session, list(hub._buffer)

    session, events = asyncio.run(run())
    status = session.status()
    assert status["finished"] is True
    assert status["error"] is None
    assert status["windows"] >= 30
    sequences = [event["sequence"] for event in events]
    assert sequences == sorted(sequences)
    assert len(set(sequences)) == len(sequences)
    assert events[0]["schema_version"] == "ws-event.v1"
    event_types = {event["event_type"] for event in events}
    assert "signal.frame" in event_types
    assert "cycle.started" in event_types
    assert "agent.claim" in event_types
    assert "agent.challenge" in event_types
    assert "synthesis.result" in event_types
    assert "session.status" in event_types
    assert "source.health" in event_types
    source_health_event = next(event for event in events if event["event_type"] == "source.health")
    source_health = source_health_event["payload"]
    assert source_health["schema_version"] == "source-health.v1"
    assert source_health["session_id"] == session.session_id
    assert source_health_event["session_id"] == session.session_id
    assert source_health["status"] in {"ok", "degraded", "stale", "error"}
    assert source_health["updated_at"]
    assert source_health["active_links"]
    assert source_health["calibration_simulated"] is True
    signal_event = next(event for event in events if event["event_type"] == "signal.frame")
    assert signal_event["payload"]["triplet"]["session_id"] == session.session_id
    cycle_started = next(event for event in events if event["event_type"] == "cycle.started")
    assert cycle_started["payload"]["signal_snapshot"]["window_id"]
    assert cycle_started["payload"]["analysis_refresh_s"] == 7.0
    last = events[-1]
    assert last["event_type"] == "session.status"
    assert last["payload"]["state"] == "finished"
    latency = session.metrics()["window_latency_ms"]
    assert 0 <= latency["p95_ms"] < 1_000
    for event in events:
        if event["event_type"] == "session.status":
            StreamStatus.model_validate(event["payload"])


def test_snapshot_recovery_returns_catch_up_after_last_sequence() -> None:
    hub = StreamHub()

    async def run():
        session = await _run_session(hub)
        assert session.status()["finished"]
        snapshot = hub.snapshot(last_sequence=5)
        return snapshot

    snapshot = asyncio.run(run())
    assert snapshot["event_type"] == "snapshot"
    assert snapshot["schema_version"] == "ws-event.v1"
    assert snapshot["session_id"] == snapshot["payload"]["status"]["session_id"]
    assert snapshot["emitted_at"]
    payload = snapshot["payload"]
    assert payload["latest_triplet"] is not None
    assert payload["latest_result"] is not None
    catch_up = payload["catch_up"]
    assert catch_up, "must replay events after last_sequence"
    assert all(event["sequence"] > 5 for event in catch_up)
    assert payload["recent_events"]
    assert payload["latest_source_health"] is not None
    assert len(hub._buffer) <= BUFFER_LIMIT


def test_controls_change_status_and_record_flag(tmp_path: Path) -> None:
    hub = StreamHub()

    async def run() -> StreamSession:
        session = StreamSession(
            bundle_root=BUNDLE,
            paced=False,
            raw_recording_dir=tmp_path,
        )
        hub.attach_session(session)
        session.start()
        await asyncio.sleep(0.05)
        session.set_rate(2.0)
        session.seek(1.5)
        session.step(10)
        await session.toggle_recording()
        status = session.status()
        assert status["rate"] == 2.0
        assert status["recording"] is True
        await session.toggle_recording()
        assert session.status()["recording"] is False
        await session.stop()
        return session

    asyncio.run(run())


def test_live_profile_never_falls_back_to_simulated(tmp_path: Path) -> None:
    simulated = demo_profile(FeatureConfig(), TEST_TOPOLOGY_HASH)
    profile_path = tmp_path / "profile.json"
    profile_path.write_text(simulated.model_dump_json(), encoding="utf-8")

    with pytest.raises(CalibrationUnavailableError, match="marked simulated"):
        _load_profile(
            TEST_TOPOLOGY_HASH,
            mode="live",
            profile_path=profile_path,
        )
    with pytest.raises(CalibrationUnavailableError, match="all-zero placeholder"):
        _load_profile(
            "sha256:" + "0" * 64,
            mode="live",
            profile_path=profile_path,
        )


def test_live_profile_accepts_current_matching_recorded_profile(tmp_path: Path) -> None:
    profile_path = tmp_path / "profile.json"
    expected = _write_live_profile(profile_path)
    loaded = _load_profile(
        TEST_TOPOLOGY_HASH,
        mode="live",
        profile_path=profile_path,
    )
    assert loaded.profile_id == expected.profile_id
    assert loaded.simulated is False


def test_live_rest_start_rejects_simulated_profile(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    hub = reset_hub_for_testing()
    monkeypatch.setenv("RX_PORTS", "rx-a=/dev/fake-a,rx-b=/dev/fake-b")
    monkeypatch.setenv(
        "LIVE_TOPOLOGY_HASH",
        "sha256:359891dec556ad665b48693024baea8f4b3c09168a8fa3c15669d1ed5d6bb58b",
    )
    try:
        response = client.post("/api/stream/start", params={"mode": "live"})
        assert response.status_code == 422
        assert "simulated" in response.json()["detail"]
        assert hub.session is None
    finally:
        reset_hub_for_testing()


def test_raw_record_toggle_publishes_verifiable_append_only_bundle(
    tmp_path: Path,
) -> None:
    hub = StreamHub()

    async def run() -> StreamSession:
        session = StreamSession(
            bundle_root=BUNDLE,
            paced=False,
            raw_recording_dir=tmp_path,
        )
        hub.attach_session(session)
        await session.toggle_recording()  # queued until the source manifest is known
        session.start()
        deadline = asyncio.get_running_loop().time() + 60
        while not session.status()["finished"] and not session.status()["error"]:
            if asyncio.get_running_loop().time() > deadline:
                raise AssertionError("recording session did not finish")
            await asyncio.sleep(0.01)
        return session

    session = asyncio.run(run())
    bundle_id = session.status()["recording_bundle_id"]
    assert bundle_id
    result = BundleVerifier(tmp_path / bundle_id).verify()
    assert result.ok, result.errors
    assert result.raw_bytes > 0
    assert result.manifest is not None
    assert result.manifest.topology_hash == session._source_manifest.topology_hash
    assert result.manifest.calibration_profile_id == session._profile.profile_id


def test_websocket_query_and_hello_resume_return_enveloped_catch_up() -> None:
    hub = reset_hub_for_testing()
    session = StreamSession(bundle_root=BUNDLE, paced=False)
    hub.attach_session(session)
    hub.publish(session.session_id, "session.status", session.status())
    try:
        with client.websocket_connect("/ws?last_sequence=0") as websocket:
            initial = websocket.receive_json()
            assert initial["schema_version"] == "ws-event.v1"
            assert initial["session_id"] == session.session_id
            assert initial["payload"]["catch_up"][0]["sequence"] == 1
            websocket.send_json({"type": "hello", "last_sequence": 0})
            resumed = websocket.receive_json()
            assert resumed["event_type"] == "snapshot"
            assert resumed["payload"]["catch_up"][0]["sequence"] == 1
    finally:
        reset_hub_for_testing()


def test_attaching_new_session_drops_previous_session_history() -> None:
    hub = StreamHub()
    first = StreamSession(bundle_root=BUNDLE, paced=False)
    hub.attach_session(first)
    hub.publish(first.session_id, "session.status", first.status())
    second = StreamSession(bundle_root=BUNDLE, paced=False)
    hub.attach_session(second)
    snapshot = hub.snapshot(last_sequence=0)
    assert snapshot["session_id"] == second.session_id
    assert snapshot["sequence"] == 0
    assert snapshot["payload"]["recent_events"] == []
    assert snapshot["payload"]["catch_up"] == []


def test_seek_resets_derived_timeline_and_step_stays_paused() -> None:
    hub = StreamHub()

    async def run() -> None:
        session = StreamSession(bundle_root=BUNDLE, paced=True, rate=4.0)
        hub.attach_session(session)
        session.start()
        deadline = asyncio.get_running_loop().time() + 10
        while session.status()["frames"] < 20:
            if asyncio.get_running_loop().time() > deadline:
                raise AssertionError("replay did not start")
            await asyncio.sleep(0.01)
        session.pause()
        while not session.status()["paused"]:
            await asyncio.sleep(0.01)

        session.seek(0.0)
        sought = session.status()
        assert sought["timeline_revision"] == 1
        assert sought["position_s"] == 0.0
        assert sought["frames"] == 0
        assert session._last_triplet is None
        assert session._last_result is None

        await session.step_and_wait(10)
        stepped = session.status()
        assert stepped["paused"] is True
        assert stepped["finished"] is False
        assert stepped["frames"] == 10
        await session.stop()

    asyncio.run(run())


def test_rest_bundles_list_and_detail() -> None:
    response = client.get("/api/replay/bundles")
    assert response.status_code == 200
    bundles = response.json()
    assert any(bundle["bundle_id"] == "walk_through" for bundle in bundles)
    walk = next(bundle for bundle in bundles if bundle["bundle_id"] == "walk_through")
    assert walk["verified"] is True
    assert walk["manifest"]["recording_id"] == "walk_through"
    detail = client.get("/api/replay/bundles/walk_through")
    assert detail.status_code == 200
    assert detail.json()["verified"] is True
    missing = client.get("/api/replay/bundles/does-not-exist")
    assert missing.status_code == 404


def test_rest_rejects_fixture_traversal_and_oversized_controls() -> None:
    hub = reset_hub_for_testing()
    traversal = client.post(
        "/api/stream/start",
        params={"mode": "replay", "bundle_id": ".."},
    )
    assert traversal.status_code == 400

    oversized = client.post(
        "/api/stream/control",
        json={"action": "step", "frames": 10_001},
    )
    assert oversized.status_code == 422
    hub.detach_session()


def test_session_controls_reject_unbounded_websocket_values() -> None:
    session = StreamSession(bundle_root=BUNDLE, paced=True)
    with pytest.raises(ValueError, match="step frames"):
        session.step(10_001)
    with pytest.raises(ValueError, match="seek seconds"):
        session.seek(float("inf"))


def test_rest_stream_start_control_stop() -> None:
    hub = get_hub()

    async def run() -> None:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://test",
        ) as http:
            started = await http.post(
                "/api/stream/start",
                params={"bundle_id": "walk_through"},
            )
            assert started.status_code == 200
            assert started.json()["bundle_id"] == "walk_through"
            status = await http.get("/api/stream/status")
            assert status.json()["running"] is True
            control = await http.post(
                "/api/stream/control",
                json={"action": "rate", "rate": 4.0},
            )
            assert control.status_code == 200
            assert control.json()["rate"] == 4.0
            stopped = await http.post("/api/stream/stop")
            assert stopped.status_code == 200

    try:
        asyncio.run(run())
    finally:
        hub.detach_session()


def test_rest_stream_conflict_when_session_exists() -> None:
    hub = get_hub()
    session = StreamSession(bundle_root=BUNDLE, paced=False)
    hub.attach_session(session)

    async def run() -> None:
        session.start()
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://test",
        ) as http:
            idempotent = await http.post(
                "/api/stream/start",
                params={"bundle_id": "walk_through"},
            )
            assert idempotent.status_code == 200
            conflict = await http.post(
                "/api/stream/start",
                params={"bundle_id": "demo_2min"},
            )
            assert conflict.status_code == 409
        await session.stop()

    try:
        asyncio.run(run())
    finally:
        hub.detach_session()
