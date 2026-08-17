"""Replay/mock/live session API: bundles, stream control, faults, metrics."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from wifi_collector.replay_bundle import BundleVerifier, ReplayManifest

from .config import (
    get_calibration_profile_path,
    get_live_topology_hash,
    get_rx_ports,
)
from .stream import (
    CalibrationUnavailableError,
    StreamSession,
    _now_iso,
    get_hub,
)

router = APIRouter(prefix="/api", tags=["replay", "stream"])

FIXTURES_DIR = Path(__file__).resolve().parents[3] / "data" / "fixtures"
BUNDLE_ID_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}")


class BundleSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    bundle_id: str = Field(min_length=1)
    verified: bool
    raw_bytes: int = 0
    manifest: ReplayManifest | None = None
    errors: list[str] = Field(default_factory=list)


class StreamStatus(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["stream-status.v1"] = "stream-status.v1"
    session_id: str | None = None
    state: Literal["idle", "starting", "running", "paused", "finished", "stopped", "error"] = "idle"
    timeline_revision: int = Field(default=0, ge=0)
    mode: str | None = None
    source_id: str | None = None
    bundle_id: str | None = None
    running: bool
    finished: bool
    paused: bool
    rate: float
    position_s: float
    demo_phase: str | None = None
    frames: int
    windows: int
    evidence_seals: int
    recording: bool
    recording_bundle_id: str | None = None
    recompute: bool
    ground_truth_present: bool = False
    faults: dict[str, dict[str, Any]] = Field(default_factory=dict)
    error: str | None = None
    updated_at: str


class ControlRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action: Literal["pause", "resume", "step", "seek", "rate", "record", "start", "stop"]
    frames: int = Field(default=1, ge=1, le=10_000)
    seconds: float = Field(default=0.0, ge=0, le=86_400)
    rate: float = Field(default=1.0, ge=0.25, le=4.0)


class FaultRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    active: bool = True
    params: dict[str, Any] = Field(default_factory=dict)


def _empty_status() -> StreamStatus:
    return StreamStatus(
        schema_version="stream-status.v1",
        state="idle",
        running=False,
        finished=False,
        paused=False,
        rate=1.0,
        position_s=0.0,
        frames=0,
        windows=0,
        evidence_seals=0,
        recording=False,
        recompute=False,
        updated_at=_now_iso(),
    )


def _status_or_empty() -> StreamStatus:
    session = get_hub().session
    return StreamStatus(**session.status()) if session is not None else _empty_status()


def _bundles() -> list[Path]:
    if not FIXTURES_DIR.is_dir():
        return []
    return sorted(
        path
        for path in FIXTURES_DIR.iterdir()
        if path.is_dir() and (path / "manifest.json").is_file()
    )


def _bundle_path(bundle_id: str) -> Path:
    """Resolve one allow-listed fixture name without path traversal."""
    if not BUNDLE_ID_PATTERN.fullmatch(bundle_id) or bundle_id in {".", ".."}:
        raise HTTPException(status_code=400, detail="invalid bundle_id")
    return FIXTURES_DIR / bundle_id


@router.get("/replay/bundles", response_model=list[BundleSummary])
def list_bundles() -> list[BundleSummary]:
    summaries: list[BundleSummary] = []
    for path in _bundles():
        result = BundleVerifier(path).verify()
        summaries.append(
            BundleSummary(
                bundle_id=path.name,
                verified=result.ok,
                raw_bytes=result.raw_bytes,
                manifest=result.manifest,
                errors=result.errors,
            )
        )
    return summaries


@router.get("/replay/bundles/{bundle_id}", response_model=BundleSummary)
def bundle_detail(bundle_id: str) -> BundleSummary:
    path = _bundle_path(bundle_id)
    if not path.is_dir():
        raise HTTPException(status_code=404, detail=f"unknown bundle {bundle_id}")
    result = BundleVerifier(path).verify()
    return BundleSummary(
        bundle_id=bundle_id,
        verified=result.ok,
        raw_bytes=result.raw_bytes,
        manifest=result.manifest,
        errors=result.errors,
    )


@router.get("/stream/status", response_model=StreamStatus)
def stream_status() -> StreamStatus:
    return _status_or_empty()


@router.post("/stream/start", response_model=StreamStatus)
async def stream_start(
    mode: Literal["replay", "mock", "live"] = "replay",
    bundle_id: str | None = None,
    scenario: str | None = None,
    demo: bool = False,
) -> StreamStatus:
    hub = get_hub()
    existing = hub.session
    if existing is not None and existing.is_running:
        same_source = existing.mode == mode and (
            (mode == "replay" and bundle_id == existing._source_id)
            or (mode == "mock" and scenario == existing._source_id)
            or mode == "live"
        )
        if same_source:
            # Idempotent start: same source already running.
            return StreamStatus(**existing.status())
        raise HTTPException(
            status_code=409,
            detail="a session with a different source is running; stop it first",
        )
    if mode == "replay":
        if not bundle_id:
            raise HTTPException(status_code=400, detail="bundle_id required for replay")
        path = _bundle_path(bundle_id)
        if not path.is_dir():
            raise HTTPException(status_code=404, detail=f"unknown bundle {bundle_id}")
        session = StreamSession(mode="replay", bundle_root=path, paced=True)
    elif mode == "mock":
        session = StreamSession(
            mode="mock",
            scenario=scenario or "walk_through",
            paced=True,
            demo_scenario=demo or scenario == "demo_2min",
        )
    else:
        session = StreamSession(
            mode="live",
            rx_ports=get_rx_ports(),
            paced=True,
            calibration_profile_path=get_calibration_profile_path(),
            live_topology_hash=get_live_topology_hash(),
        )
        try:
            session.validate_live_configuration()
        except CalibrationUnavailableError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
    hub.attach_session(session)
    session.start()
    return StreamStatus(**session.status())


@router.post("/stream/control", response_model=StreamStatus)
async def stream_control(request: ControlRequest) -> StreamStatus:
    session = get_hub().session
    if session is None:
        raise HTTPException(status_code=409, detail="no active session")
    if request.action == "pause":
        session.pause()
    elif request.action == "resume":
        session.resume()
    elif request.action == "step":
        await session.step_and_wait(request.frames)
    elif request.action == "seek":
        session.seek(request.seconds)
    elif request.action == "rate":
        session.set_rate(request.rate)
    elif request.action == "record":
        await session.toggle_recording()
    elif request.action == "start":
        session.start()
    elif request.action == "stop":
        await session.stop()
    return StreamStatus(**session.status())


@router.post("/stream/stop", response_model=StreamStatus)
async def stream_stop() -> StreamStatus:
    session = get_hub().session
    if session is None:
        return _empty_status()
    await session.stop()
    return StreamStatus(**session.status())


@router.get("/stream/metrics", response_model=dict[str, Any])
def stream_metrics() -> dict[str, Any]:
    session = get_hub().session
    return session.metrics() if session is not None else {"session_id": None}


@router.get("/stream/faults", response_model=dict[str, dict[str, Any]])
def stream_faults() -> dict[str, dict[str, Any]]:
    session = get_hub().session
    return session.faults_summary() if session is not None else {}


@router.post("/stream/faults/{fault}", response_model=dict[str, Any])
def stream_fault(fault: str, request: FaultRequest) -> dict[str, Any]:
    session = get_hub().session
    if session is None:
        raise HTTPException(status_code=409, detail="no active session")
    if request.active:
        session.activate_fault(fault, request.params)
    else:
        session.deactivate_fault(fault)
    return {"active": session.faults_summary().get(fault, {}) is not None}
