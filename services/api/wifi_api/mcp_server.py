"""Focused MCP adapter over the active WiFi Spatial Council session.

The MCP server is intentionally an adapter, not a second application runtime:
tools read ``get_hub().session`` and compact sealed evidence. It never starts
sources, reads raw CSI, or accepts filesystem paths. One tool may execute a
bounded real-provider Council and cache it. The Streamable HTTP ASGI app is mounted by ``app.py`` at
``/mcp``; Starlette canonicalizes the mounted endpoint to ``/mcp/`` and the
official MCP client follows that redirect.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Literal

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations
from pydantic import BaseModel, ConfigDict, Field
from wifi_contracts import (
    CouncilCycleDetail,
    CouncilResult,
    ProviderHealth,
    SignalTriplet,
    SourceMode,
)
from wifi_council.config import CouncilConfig
from wifi_council.runtime import build_provider

from .agent_routes import (
    TRUTH_BOUNDARY,
    AgentInvokeRequest,
    AgentQueryRequest,
    AgentReading,
)
from .agent_routes import invoke_agent as invoke_agent_api
from .agent_routes import (
    query_agent_reading as query_agent_reading_api,
)
from .config import (
    APP_VERSION,
    SERVICE_NAME,
    public_real_provider_invoke,
    public_replay,
    real_agent_provider,
)
from .replay_routes import list_bundles
from .stream import StreamSession, get_hub

MCP_SCHEMA_VERSION: Literal["mcp-tool-response.v1"] = "mcp-tool-response.v1"
SENSING_PROVIDER = "wifi_sensing deterministic proxy pipeline"

READ_ONLY_ANNOTATIONS = ToolAnnotations(
    readOnlyHint=True,
    destructiveHint=False,
    idempotentHint=True,
    openWorldHint=False,
)

AGENT_INVOKE_ANNOTATIONS = ToolAnnotations(
    readOnlyHint=False,
    destructiveHint=False,
    idempotentHint=True,
    openWorldHint=True,
)


class ToolQuality(BaseModel):
    """Quality stays explicit instead of being inferred from Agent agreement."""

    model_config = ConfigDict(extra="forbid")

    status: Literal["ok", "degraded", "unknown"]
    sensor_confidence_cap: float | None = Field(default=None, ge=0, le=1)
    detail: str = Field(min_length=1)


class ProviderProvenance(BaseModel):
    """Provider identity without credentials, request headers, or paths."""

    model_config = ConfigDict(extra="forbid")

    sensing_provider: str = SENSING_PROVIDER
    council_provider: str | None = None
    council_model: str | None = None
    council_status: str | None = None
    real_model_calls: int = Field(default=0, ge=0)
    source_is_simulated: bool | None = None


class McpToolResponse(BaseModel):
    """Fields common to every externally callable MCP tool."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["mcp-tool-response.v1"] = MCP_SCHEMA_VERSION
    session_id: str | None
    source_mode: SourceMode | None
    generated_at: datetime
    quality: ToolQuality
    truth_boundary: list[str]
    provider_provenance: ProviderProvenance


class SafeStreamState(BaseModel):
    """Allow-listed stream status; errors/fault params and paths stay private."""

    model_config = ConfigDict(extra="forbid")

    session_id: str
    state: str
    mode: SourceMode
    source_id: str
    running: bool
    finished: bool
    paused: bool
    position_s: float = Field(ge=0)
    frames: int = Field(ge=0)
    windows: int = Field(ge=0)
    evidence_seals: int = Field(ge=0)


class SafeSourceHealth(BaseModel):
    """Allow-listed source health containing counters, never raw frames."""

    model_config = ConfigDict(extra="forbid")

    status: str
    active_links: list[str] = Field(default_factory=list)
    degraded_links: list[str] = Field(default_factory=list)
    dropped_links: list[str] = Field(default_factory=list)
    counters: dict[str, int] = Field(default_factory=dict)
    calibration_simulated: bool | None = None
    calibration_state: str | None = None
    channel: int | None = None
    bandwidth_mhz: int | None = None
    updated_at: datetime | None = None


class SystemHealthResponse(McpToolResponse):
    service: str
    version: str
    status: Literal["ok", "degraded"]
    public_replay_read_only: bool
    stream: SafeStreamState | None
    source_health: SafeSourceHealth | None
    provider_health: ProviderHealth | None
    real_agent_invoke_enabled: bool
    invocation_provider_health: ProviderHealth | None


class ReplayBundleInfo(BaseModel):
    """Replay metadata that cannot be used to access files or raw CSI."""

    model_config = ConfigDict(extra="forbid")

    bundle_id: str
    verified: bool
    raw_bytes: int = Field(ge=0)
    recorded_source_mode: SourceMode | None
    ground_truth_present: bool
    privacy: str | None
    errors: list[str] = Field(default_factory=list)


class ReplayBundlesResponse(McpToolResponse):
    bundles: list[ReplayBundleInfo]


class SpatialReadingResponse(McpToolResponse):
    status: Literal["ready", "degraded", "unavailable"]
    stream_state: str | None
    reading: SignalTriplet | None


class AgentQueryResponse(McpToolResponse):
    # ``status`` describes delivery/provider execution. ``cycle_status`` is
    # the honest semantic conclusion and may be ``ambiguous`` on a ready call.
    status: Literal["ready", "waiting", "degraded", "unavailable"]
    cycle_status: Literal["supported", "ambiguous", "unavailable"] | None
    reading: AgentReading


class CouncilResultResponse(McpToolResponse):
    status: Literal["ready", "degraded", "unavailable"]
    cycle_id: str | None
    cycle_status: str | None
    result: CouncilResult | None
    cycle: CouncilCycleDetail | None


def _active_cycle(session: StreamSession | None) -> CouncilCycleDetail | None:
    if session is None or session.council_runtime is None:
        return None
    return session.council_runtime.store.current


def _provider_health(session: StreamSession | None) -> ProviderHealth | None:
    if session is None or session.council_runtime is None:
        return None
    return session.council_runtime.provider.health()


def _real_model_calls(
    cycle: CouncilCycleDetail | None,
    health: ProviderHealth | None,
) -> int:
    if cycle is None or health is None or health.provider == "mock":
        return 0
    return sum(record.status == "ok" for record in cycle.calls)


def _source_is_simulated(session: StreamSession | None) -> bool | None:
    if session is None:
        return None
    source_health = session.latest_source_health or {}
    recorded_mode = source_health.get("source_mode")
    calibration_simulated = source_health.get("calibration_simulated")
    return bool(session.mode == "mock" or recorded_mode == "mock" or calibration_simulated is True)


def _provenance(
    session: StreamSession | None,
    cycle: CouncilCycleDetail | None = None,
) -> ProviderProvenance:
    health = _provider_health(session)
    return ProviderProvenance(
        council_provider=health.provider if health is not None else None,
        council_model=health.model if health is not None else None,
        council_status=health.status if health is not None else None,
        real_model_calls=_real_model_calls(cycle, health),
        source_is_simulated=_source_is_simulated(session),
    )


def _quality(
    session: StreamSession | None,
    triplet: SignalTriplet | None = None,
) -> ToolQuality:
    if session is None:
        return ToolQuality(status="unknown", detail="no active stream session")
    source_health = session.latest_source_health or {}
    source_status = str(source_health.get("status", "ok"))
    if triplet is None:
        if source_status in {"degraded", "stale", "error"}:
            return ToolQuality(
                status="degraded",
                detail=f"source health is {source_status}",
            )
        return ToolQuality(
            status="unknown",
            detail="stream active; no spatial reading is available yet",
        )
    if triplet.status == "ok" and source_status == "ok":
        status: Literal["ok", "degraded", "unknown"] = "ok"
    elif triplet.status in {"degraded"} or source_status in {
        "degraded",
        "stale",
        "error",
    }:
        status = "degraded"
    else:
        status = "unknown"
    return ToolQuality(
        status=status,
        sensor_confidence_cap=triplet.sensor_confidence_cap,
        detail=(
            f"signal status={triplet.status}; source health={source_status}; "
            "Agent agreement is excluded from this quality"
        ),
    )


def _base_fields(
    session: StreamSession | None,
    *,
    triplet: SignalTriplet | None = None,
    cycle: CouncilCycleDetail | None = None,
) -> dict[str, Any]:
    return {
        "session_id": session.session_id if session is not None else None,
        "source_mode": session.mode if session is not None else None,
        "generated_at": datetime.now(UTC),
        "quality": _quality(session, triplet),
        "truth_boundary": list(TRUTH_BOUNDARY),
        "provider_provenance": _provenance(session, cycle),
    }


def _latest_triplet(session: StreamSession | None) -> SignalTriplet | None:
    if session is None:
        return None
    payload = session.snapshot()["payload"].get("latest_triplet")
    return SignalTriplet.model_validate(payload) if payload is not None else None


def _safe_stream(session: StreamSession | None) -> SafeStreamState | None:
    if session is None:
        return None
    status = session.status()
    return SafeStreamState(
        session_id=session.session_id,
        state=str(status["state"]),
        mode=session.mode,
        source_id=str(status["source_id"]),
        running=bool(status["running"]),
        finished=bool(status["finished"]),
        paused=bool(status["paused"]),
        position_s=float(status["position_s"]),
        frames=int(status["frames"]),
        windows=int(status["windows"]),
        evidence_seals=int(status["evidence_seals"]),
    )


def _safe_source_health(session: StreamSession | None) -> SafeSourceHealth | None:
    if session is None or session.latest_source_health is None:
        return None
    health = session.latest_source_health
    return SafeSourceHealth(
        status=str(health.get("status", "unknown")),
        active_links=[str(value) for value in health.get("active_links", [])],
        degraded_links=[str(value) for value in health.get("degraded_links", [])],
        dropped_links=[str(value) for value in health.get("dropped_links", [])],
        counters={str(key): int(value) for key, value in health.get("counters", {}).items()},
        calibration_simulated=health.get("calibration_simulated"),
        calibration_state=health.get("calibration_state"),
        channel=health.get("channel"),
        bandwidth_mhz=health.get("bandwidth_mhz"),
        updated_at=health.get("updated_at"),
    )


def _safe_cycle(cycle: CouncilCycleDetail | None) -> CouncilCycleDetail | None:
    """Redact free-form provider errors, which may contain host-local details."""
    if cycle is None:
        return None
    calls = [
        record.model_copy(
            update={
                "error": (
                    "provider call failed; server-side detail redacted"
                    if record.error is not None
                    else None
                )
            }
        )
        for record in cycle.calls
    ]
    return cycle.model_copy(update={"calls": calls})


def get_system_health() -> dict[str, Any]:
    """Return safe API, stream, source, and active Agent-provider health."""
    session = get_hub().session
    status = session.status() if session is not None else None
    source_health = session.latest_source_health if session is not None else None
    degraded = bool(
        (status is not None and status["state"] == "error")
        or (source_health is not None and source_health.get("status") != "ok")
    )
    response = SystemHealthResponse(
        **_base_fields(session, triplet=_latest_triplet(session), cycle=_active_cycle(session)),
        service=SERVICE_NAME,
        version=APP_VERSION,
        status="degraded" if degraded else "ok",
        public_replay_read_only=public_replay(),
        stream=_safe_stream(session),
        source_health=_safe_source_health(session),
        provider_health=_provider_health(session),
        real_agent_invoke_enabled=public_real_provider_invoke(),
        invocation_provider_health=(
            build_provider(CouncilConfig(), real_agent_provider()).health()
            if public_real_provider_invoke()
            else None
        ),
    )
    return response.model_dump(mode="json")


def list_replay_bundles() -> dict[str, Any]:
    """List allow-listed, checksum-verified Replay metadata; never return raw CSI."""
    session = get_hub().session
    summaries = list_bundles()
    bundles = [
        ReplayBundleInfo(
            bundle_id=summary.bundle_id,
            verified=summary.verified,
            raw_bytes=summary.raw_bytes,
            recorded_source_mode=(
                summary.manifest.source_mode if summary.manifest is not None else None
            ),
            ground_truth_present=(
                summary.manifest.ground_truth_present if summary.manifest is not None else False
            ),
            privacy=summary.manifest.privacy if summary.manifest is not None else None,
            errors=["bundle verification failed; detail redacted"] if summary.errors else [],
        )
        for summary in summaries
    ]
    if not bundles:
        quality = ToolQuality(status="unknown", detail="no Replay bundles are available")
    elif all(bundle.verified for bundle in bundles):
        quality = ToolQuality(status="ok", detail="all listed Replay bundles verified")
    else:
        quality = ToolQuality(status="degraded", detail="one or more Replay bundles failed")
    base = _base_fields(session, cycle=_active_cycle(session))
    base["quality"] = quality
    response = ReplayBundlesResponse(**base, bundles=bundles)
    return response.model_dump(mode="json")


def get_latest_spatial_reading() -> dict[str, Any]:
    """Return the latest three calibrated proxy signals from the active session."""
    session = get_hub().session
    triplet = _latest_triplet(session)
    if triplet is None:
        status: Literal["ready", "degraded", "unavailable"] = "unavailable"
    elif triplet.status == "ok":
        status = "ready"
    else:
        status = "degraded"
    response = SpatialReadingResponse(
        **_base_fields(session, triplet=triplet, cycle=_active_cycle(session)),
        status=status,
        stream_state=str(session.status()["state"]) if session is not None else None,
        reading=triplet,
    )
    return response.model_dump(mode="json")


async def query_agent_reading(
    focus: Literal["overview", "activity", "occupancy", "depth", "limitations"] = "overview",
    wait_timeout_s: float = 5.0,
    require_openai: bool = False,
    require_provider: Literal["openai", "deepseek"] | None = None,
) -> dict[str, Any]:
    """Wait briefly for the active session's audited Agent reading; start nothing."""
    request = AgentQueryRequest(
        focus=focus,
        wait_timeout_s=wait_timeout_s,
        require_openai=require_openai,
        require_provider=require_provider,
    )
    reading = await query_agent_reading_api(request)
    session = get_hub().session
    triplet = reading.latest_triplet
    safe_cycle = _safe_cycle(reading.council_cycle)
    safe_reading = reading.model_copy(update={"council_cycle": safe_cycle})
    same_session = session is not None and session.session_id == reading.session_id
    base = _base_fields(
        session if same_session else None,
        triplet=triplet,
        cycle=safe_cycle,
    )
    # The public demo rolls to a fresh session every two minutes. The REST
    # query is an atomic reading from the prior session, so never combine it
    # with provenance from a newly attached session during that tiny race.
    if not same_session:
        health = reading.provider_health
        base.update(
            session_id=reading.session_id,
            source_mode=reading.source_mode,
            quality=ToolQuality(
                status=(
                    "ok"
                    if triplet is not None and triplet.status == "ok"
                    else "degraded" if triplet is not None else "unknown"
                ),
                sensor_confidence_cap=(
                    triplet.sensor_confidence_cap if triplet is not None else None
                ),
                detail="reading captured at a session rollover; source health not mixed",
            ),
            provider_provenance=ProviderProvenance(
                council_provider=reading.provider,
                council_model=health.model if health is not None else None,
                council_status=health.status if health is not None else None,
                real_model_calls=reading.real_model_calls,
                source_is_simulated=(True if reading.source_mode == "mock" else None),
            ),
        )
    response = AgentQueryResponse(
        **base,
        status=reading.status,
        cycle_status=reading.cycle_status,
        reading=safe_reading,
    )
    return response.model_dump(mode="json")


async def invoke_room_echo(
    focus: Literal["overview", "activity", "occupancy", "depth", "limitations"] = "overview",
    evidence_wait_timeout_s: float = 15.0,
) -> dict[str, Any]:
    """Run one cached real-provider Council cycle over sealed Replay evidence.

    This is the competition-facing Agent entry point. It may contact the
    configured server-side model provider, but it cannot start, pause, seek,
    record, fault, or otherwise mutate the sensing session.
    """
    reading = await invoke_agent_api(
        AgentInvokeRequest(
            focus=focus,
            evidence_wait_timeout_s=evidence_wait_timeout_s,
        )
    )
    session = get_hub().session
    safe_cycle = _safe_cycle(reading.council_cycle)
    safe_reading = reading.model_copy(update={"council_cycle": safe_cycle})
    base = _base_fields(
        session,
        triplet=reading.latest_triplet,
        cycle=safe_cycle,
    )
    health = reading.provider_health
    base.update(
        session_id=reading.session_id,
        source_mode=reading.source_mode,
        provider_provenance=ProviderProvenance(
            council_provider=reading.provider,
            council_model=health.model if health is not None else None,
            council_status=health.status if health is not None else None,
            real_model_calls=reading.real_model_calls,
            source_is_simulated=_source_is_simulated(session),
        ),
    )
    return AgentQueryResponse(
        **base,
        status=reading.status,
        cycle_status=reading.cycle_status,
        reading=safe_reading,
    ).model_dump(mode="json")


def get_latest_council_result() -> dict[str, Any]:
    """Return the latest completed result from the active stream's council store."""
    session = get_hub().session
    cycle = _safe_cycle(_active_cycle(session))
    result = cycle.result if cycle is not None else None
    if result is None:
        status: Literal["ready", "degraded", "unavailable"] = "unavailable"
    else:
        status = "ready"
    response = CouncilResultResponse(
        **_base_fields(session, triplet=_latest_triplet(session), cycle=cycle),
        status=status,
        cycle_id=cycle.cycle_id if cycle is not None else None,
        cycle_status=cycle.status if cycle is not None else None,
        result=result,
        cycle=cycle,
    )
    return response.model_dump(mode="json")


def create_mcp_server() -> FastMCP:
    """Build an isolated MCP server with the canonical read-only tool set.

    ``StreamableHTTPSessionManager`` instances deliberately run only once.
    Keeping construction explicit lets protocol tests own an isolated manager
    while the production FastAPI lifespan owns exactly one process-level
    instance.
    """
    server = FastMCP(
        name="WiFi Spatial Council",
        instructions=(
            "Read-only access to the active WiFi Spatial Council Replay session. "
            "Outputs are calibrated proxy readings and auditable Agent interpretations, "
            "not camera images, identity, person counts, poses, behaviour, emotions, or "
            "metric depth. Never treat interpretation agreement as sensor confidence."
        ),
        host="0.0.0.0",
        streamable_http_path="/",
        json_response=True,
        stateless_http=True,
        max_request_body_size=65_536,
    )
    server.tool(
        annotations=READ_ONLY_ANNOTATIONS,
        structured_output=True,
    )(get_system_health)
    server.tool(
        annotations=AGENT_INVOKE_ANNOTATIONS,
        structured_output=True,
    )(invoke_room_echo)
    return server


# This child ASGI application's root route becomes /mcp/ after FastAPI mounts
# it at /mcp. Official MCP HTTP clients follow the /mcp -> /mcp/ redirect.
mcp_server = create_mcp_server()
mcp_http_app = mcp_server.streamable_http_app()
