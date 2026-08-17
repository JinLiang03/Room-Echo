"""FastAPI application exposing the health endpoint."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager, suppress
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from fastapi import FastAPI
from pydantic import BaseModel
from wifi_contracts import CONTRACT_SCHEMAS, CONTRACTS_VERSION, SourceMode, schema_for

from .config import (
    APP_MODE,
    APP_VERSION,
    SERVICE_NAME,
    demo_autostart,
    demo_loop,
    get_app_mode,
    get_calibration_profile_path,
    get_live_topology_hash,
    get_rx_ports,
    get_scenario,
)
from .council_routes import router as council_router
from .replay_routes import router as replay_router
from .stream import StreamSession, get_hub
from .ws import router as ws_router


class ComponentHealth(BaseModel):
    status: Literal["ok", "degraded", "not_implemented", "error"]
    detail: str


class HealthResponse(BaseModel):
    status: Literal["ok", "degraded"]
    service: str
    version: str
    mode: SourceMode
    contracts_version: str
    components: dict[str, ComponentHealth]
    checked_at: datetime


def _build_demo_session(mode: SourceMode, scenario: str) -> StreamSession:
    if mode == "replay":
        return StreamSession(
            mode="replay",
            bundle_root=Path("data/fixtures") / scenario,
            paced=True,
        )
    if mode == "mock":
        return StreamSession(
            mode="mock",
            scenario=scenario,
            paced=True,
            demo_scenario=scenario == "demo_2min",
        )
    session = StreamSession(
        mode="live",
        rx_ports=get_rx_ports(),
        paced=True,
        calibration_profile_path=get_calibration_profile_path(),
        live_topology_hash=get_live_topology_hash(),
    )
    session.validate_live_configuration()
    return session


async def _run_demo_loop(
    initial_session: StreamSession,
    *,
    mode: SourceMode,
    scenario: str,
    restart_delay_s: float = 0.5,
) -> None:
    """Repeat one presentation source while it remains supervisor-owned.

    A fresh ``StreamSession`` gives every iteration a new session id.  The
    identity checks on both sides of the delay make a manual REST/WS start win
    the race instead of being overwritten by the presentation supervisor.
    """
    if mode == "live":
        raise ValueError("DEMO_LOOP is restricted to replay/mock; live never loops")

    hub = get_hub()
    session = initial_session
    while True:
        await session.wait_finished()
        if hub.session is not session or session.status()["state"] != "finished":
            return
        await asyncio.sleep(max(0.0, restart_delay_s))
        if hub.session is not session or session.status()["state"] != "finished":
            return
        session = _build_demo_session(mode, scenario)
        hub.attach_session(session)
        session.start()


@asynccontextmanager
async def _lifespan(_app: FastAPI) -> AsyncIterator[None]:
    loop_task: asyncio.Task[None] | None = None
    if demo_autostart():
        mode = get_app_mode()
        scenario = get_scenario()
        looping = demo_loop()
        if looping and mode == "live":
            raise ValueError("DEMO_LOOP is restricted to replay/mock; live never loops")
        session = _build_demo_session(mode, scenario)
        get_hub().attach_session(session)
        session.start()
        if looping:
            loop_task = asyncio.create_task(
                _run_demo_loop(session, mode=mode, scenario=scenario)
            )
    try:
        yield
    finally:
        if loop_task is not None:
            loop_task.cancel()
            with suppress(asyncio.CancelledError):
                await loop_task
        active_session = get_hub().session
        if active_session is not None:
            await active_session.stop()
            get_hub().detach_session()


app = FastAPI(
    title="WiFi Spatial Council API",
    version=APP_VERSION,
    lifespan=_lifespan,
)
app.include_router(council_router)
app.include_router(replay_router)
app.include_router(ws_router)


def _component_health() -> tuple[Literal["ok", "degraded"], dict[str, ComponentHealth]]:
    session = get_hub().session
    session_status = session.status() if session is not None else None
    stream_error = bool(session_status and session_status["state"] == "error")
    latest_source_health = session.latest_source_health if session is not None else None
    source_status = (
        str(latest_source_health.get("status", "ok")) if latest_source_health is not None else "ok"
    )
    runtime_component_status: Literal["ok", "degraded", "error"] = "ok"
    if stream_error or source_status == "error":
        runtime_component_status = "error"
    elif source_status in {"degraded", "stale"}:
        runtime_component_status = "degraded"
    collector_detail = "frame sources ready; no active session"
    sensing_detail = "deterministic sensing ready; no active session"
    if session_status is not None:
        collector_detail = (
            f"{session_status['mode']} session {session_status['state']}; "
            f"source={source_status}; frames={session_status['frames']}"
        )
        sensing_detail = (
            f"deterministic sensing {session_status['state']}; windows={session_status['windows']}"
        )
    components: dict[str, ComponentHealth] = {
        "api": ComponentHealth(status="ok", detail="http service healthy"),
        "collector": ComponentHealth(
            status=runtime_component_status,
            detail=collector_detail,
        ),
        "sensing": ComponentHealth(
            status=runtime_component_status,
            detail=sensing_detail,
        ),
        "council": ComponentHealth(
            status="ok",
            detail="agent council with policy arbiter and audit store",
        ),
    }
    try:
        for name, _model in CONTRACT_SCHEMAS:
            schema = schema_for(name)
            if schema.get("type") != "object":
                raise ValueError(f"contract {name} is not an object schema")
        components["contracts"] = ComponentHealth(
            status="ok",
            detail="all Pydantic contracts compile to JSON Schema",
        )
    except (KeyError, ValueError):
        components["contracts"] = ComponentHealth(
            status="error",
            detail="contract schema generation failed",
        )
    overall: Literal["ok", "degraded"] = (
        "ok" if all(component.status == "ok" for component in components.values()) else "degraded"
    )
    return overall, components


@app.get("/healthz", response_model=HealthResponse, tags=["ops"])
def healthz() -> HealthResponse:
    status, components = _component_health()
    session = get_hub().session
    return HealthResponse(
        status=status,
        service=SERVICE_NAME,
        version=APP_VERSION,
        mode=session.mode if session is not None else APP_MODE,
        contracts_version=CONTRACTS_VERSION,
        components=components,
        checked_at=datetime.now(UTC),
    )
