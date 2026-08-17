"""Presentation loop ownership and Live-mode safety."""

from __future__ import annotations

import asyncio
from typing import Any

import pytest
import wifi_api.app as app_module
from wifi_api.config import demo_loop


class _FakeHub:
    def __init__(self) -> None:
        self.session: Any | None = None
        self.attached: list[Any] = []

    def attach_session(self, session: Any) -> None:
        self.session = session
        self.attached.append(session)


class _FakeSession:
    def __init__(
        self,
        session_id: str,
        hub: _FakeHub,
        *,
        state: str = "finished",
        replace_with: Any | None = None,
    ) -> None:
        self.session_id = session_id
        self._hub = hub
        self._state = state
        self._replace_with = replace_with
        self.started = False

    def start(self) -> None:
        self.started = True

    async def wait_finished(self) -> None:
        await asyncio.sleep(0)
        if self._replace_with is not None:
            self._hub.session = self._replace_with

    def status(self) -> dict[str, str]:
        return {"state": self._state}


def test_demo_loop_config_is_opt_in(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DEMO_LOOP", raising=False)
    assert demo_loop() is False
    monkeypatch.setenv("DEMO_LOOP", "1")
    assert demo_loop() is True
    monkeypatch.setenv("DEMO_LOOP", "true")
    assert demo_loop() is False


def test_demo_loop_restarts_with_a_fresh_session_id(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    hub = _FakeHub()
    manual = object()
    initial = _FakeSession("replay-demo-first", hub)
    hub.attach_session(initial)
    built: list[_FakeSession] = []

    def build(mode: str, scenario: str) -> _FakeSession:
        assert mode == "replay"
        assert scenario == "demo_2min"
        session = _FakeSession(
            f"replay-demo-{len(built) + 2}",
            hub,
            replace_with=manual,
        )
        built.append(session)
        return session

    monkeypatch.setattr(app_module, "get_hub", lambda: hub)
    monkeypatch.setattr(app_module, "_build_demo_session", build)

    asyncio.run(
        app_module._run_demo_loop(
            initial,
            mode="replay",
            scenario="demo_2min",
            restart_delay_s=0,
        )
    )

    assert [item.session_id for item in hub.attached] == [
        "replay-demo-first",
        "replay-demo-2",
    ]
    assert built[0].started is True
    assert hub.session is manual


def test_real_demo_session_factory_generates_distinct_ids() -> None:
    first = app_module._build_demo_session("mock", "demo_2min")
    second = app_module._build_demo_session("mock", "demo_2min")

    assert first.session_id != second.session_id
    assert first.mode == second.mode == "mock"


def test_demo_loop_does_not_restart_an_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    hub = _FakeHub()
    failed = _FakeSession("mock-failed", hub, state="error")
    hub.attach_session(failed)
    builds = 0

    def build(_mode: str, _scenario: str) -> _FakeSession:
        nonlocal builds
        builds += 1
        return _FakeSession("unexpected", hub)

    monkeypatch.setattr(app_module, "get_hub", lambda: hub)
    monkeypatch.setattr(app_module, "_build_demo_session", build)

    asyncio.run(
        app_module._run_demo_loop(
            failed,
            mode="mock",
            scenario="demo_2min",
            restart_delay_s=0,
        )
    )
    assert builds == 0
    assert hub.session is failed


def test_manual_session_replacement_wins_over_supervisor(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    hub = _FakeHub()
    manual = object()
    initial = _FakeSession(
        "replay-autostart",
        hub,
        replace_with=manual,
    )
    hub.attach_session(initial)
    builds = 0

    def build(_mode: str, _scenario: str) -> _FakeSession:
        nonlocal builds
        builds += 1
        return _FakeSession("unexpected", hub)

    monkeypatch.setattr(app_module, "get_hub", lambda: hub)
    monkeypatch.setattr(app_module, "_build_demo_session", build)

    asyncio.run(
        app_module._run_demo_loop(
            initial,
            mode="replay",
            scenario="demo_2min",
            restart_delay_s=0,
        )
    )
    assert builds == 0
    assert hub.session is manual


def test_manual_restart_of_same_session_wins_during_loop_delay(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    hub = _FakeHub()
    initial = _FakeSession("replay-autostart", hub)
    hub.attach_session(initial)
    builds = 0

    def build(_mode: str, _scenario: str) -> _FakeSession:
        nonlocal builds
        builds += 1
        return _FakeSession("unexpected", hub)

    monkeypatch.setattr(app_module, "get_hub", lambda: hub)
    monkeypatch.setattr(app_module, "_build_demo_session", build)

    async def run() -> None:
        supervisor = asyncio.create_task(
            app_module._run_demo_loop(
                initial,
                mode="replay",
                scenario="demo_2min",
                restart_delay_s=0.02,
            )
        )
        await asyncio.sleep(0.005)
        initial._state = "starting"
        await supervisor

    asyncio.run(run())
    assert builds == 0
    assert hub.session is initial


def test_demo_loop_rejects_live_before_building_or_attaching(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    hub = _FakeHub()
    initial = _FakeSession("live-initial", hub)
    hub.attach_session(initial)
    builds = 0

    def build(_mode: str, _scenario: str) -> _FakeSession:
        nonlocal builds
        builds += 1
        return _FakeSession("unexpected", hub)

    monkeypatch.setattr(app_module, "get_hub", lambda: hub)
    monkeypatch.setattr(app_module, "_build_demo_session", build)

    with pytest.raises(ValueError, match="live never loops"):
        asyncio.run(
            app_module._run_demo_loop(
                initial,
                mode="live",
                scenario="ignored",
                restart_delay_s=0,
            )
        )
    assert builds == 0
    assert hub.attached == [initial]


def test_lifespan_rejects_live_loop_before_session_construction(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    builds = 0

    def build(_mode: str, _scenario: str) -> _FakeSession:
        nonlocal builds
        builds += 1
        raise AssertionError("Live loop must fail before building a session")

    monkeypatch.setattr(app_module, "demo_autostart", lambda: True)
    monkeypatch.setattr(app_module, "demo_loop", lambda: True)
    monkeypatch.setattr(app_module, "get_app_mode", lambda: "live")
    monkeypatch.setattr(app_module, "get_scenario", lambda: "ignored")
    monkeypatch.setattr(app_module, "_build_demo_session", build)

    async def enter_lifespan() -> None:
        async with app_module._lifespan(app_module.app):
            raise AssertionError("Live looping lifespan must not start")

    with pytest.raises(ValueError, match="live never loops"):
        asyncio.run(enter_lifespan())
    assert builds == 0
