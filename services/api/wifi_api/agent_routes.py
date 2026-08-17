"""Narrow, read-only Agent query endpoints for delivery evaluation.

The stream remains the owner of sensing and council execution.  These routes
make the latest completed, audited cycle easy to evaluate without exposing raw
CSI or adding a second orchestration path.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from time import perf_counter
from typing import Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from wifi_contracts import (
    CouncilCycleDetail,
    CouncilUsageSummary,
    ProviderHealth,
    SignalTriplet,
    SourceMode,
)

from .real_provider import (
    RealProviderIncomplete,
    RealProviderUnavailable,
    get_verified_runner,
)
from .stream import StreamSession, get_hub

router = APIRouter(prefix="/api/agent", tags=["agent"])

Focus = Literal["overview", "activity", "occupancy", "depth", "limitations"]
RealProvider = Literal["openai", "deepseek"]
CycleStatus = Literal["supported", "ambiguous", "unavailable"]

TRUTH_BOUNDARY = [
    "inference field, not a camera image",
    "no identity, person count, pose, behaviour, or emotion recognition",
    "occupancy and depth are calibrated relative proxies, not metric measurements",
    "final claim confidence never exceeds the sensor confidence cap",
]


class AgentQueryRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    focus: Focus = "overview"
    wait_timeout_s: float = Field(default=5.0, ge=0.0, le=15.0)
    require_openai: bool = False
    require_provider: RealProvider | None = None


class AgentInvokeRequest(BaseModel):
    """One evaluator-facing, synchronous real Council invocation."""

    model_config = ConfigDict(extra="forbid")

    focus: Focus = "overview"
    evidence_wait_timeout_s: float = Field(default=15.0, ge=0.0, le=30.0)


class AgentReading(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["agent-reading.v1"] = "agent-reading.v1"
    # Delivery/execution state is intentionally separate from the Council's
    # semantic conclusion. A completed provider call can be ready even when
    # the evidence is honestly ambiguous.
    status: Literal["ready", "waiting", "degraded", "unavailable"]
    cycle_status: CycleStatus | None
    focus: Focus
    session_id: str | None
    source_mode: SourceMode | None
    stream_state: str | None
    provider: str | None
    provider_health: ProviderHealth | None
    real_model_calls: int = Field(ge=0)
    latest_triplet: SignalTriplet | None
    council_cycle: CouncilCycleDetail | None
    usage: CouncilUsageSummary | None
    response_latency_ms: float = Field(ge=0)
    generated_at: datetime
    truth_boundary: list[str]


def _current_parts(
    session: StreamSession | None,
) -> tuple[
    SignalTriplet | None,
    CouncilCycleDetail | None,
    ProviderHealth | None,
    CouncilUsageSummary | None,
]:
    if session is None:
        return None, None, None, None
    snapshot = session.snapshot()["payload"]
    triplet_payload = snapshot.get("latest_triplet")
    triplet = (
        SignalTriplet.model_validate(triplet_payload)
        if triplet_payload is not None
        else None
    )
    runtime = session.council_runtime
    if runtime is None:
        return triplet, None, None, None
    return (
        triplet,
        runtime.store.current,
        runtime.provider.health(),
        runtime.store.usage_summary(),
    )


def _real_model_call_count(
    cycle: CouncilCycleDetail | None,
    health: ProviderHealth | None,
) -> int:
    if cycle is None or health is None or health.provider == "mock":
        return 0
    return sum(record.status == "ok" for record in cycle.calls)


async def _query(request: AgentQueryRequest) -> AgentReading:
    started = perf_counter()
    deadline = asyncio.get_running_loop().time() + request.wait_timeout_s
    session = get_hub().session
    triplet, cycle, provider_health, usage = _current_parts(session)
    while session is not None and cycle is None and asyncio.get_running_loop().time() < deadline:
        await asyncio.sleep(0.05)
        session = get_hub().session
        triplet, cycle, provider_health, usage = _current_parts(session)

    model_calls = _real_model_call_count(cycle, provider_health)
    required_provider: RealProvider | None = (
        "openai" if request.require_openai else request.require_provider
    )
    if required_provider is not None and (
        provider_health is None
        or provider_health.provider != required_provider
        or provider_health.status != "ok"
        or model_calls == 0
    ):
        raise HTTPException(
            status_code=503,
            detail=(
                f"a completed, healthy {required_provider}-backed council cycle is not available; "
                "mock output is never presented as a real model call"
            ),
        )

    if session is None:
        status: Literal["ready", "waiting", "degraded", "unavailable"] = "unavailable"
        stream_state = None
        session_id = None
        source_mode = None
    else:
        session_status = session.status()
        stream_state = str(session_status["state"])
        session_id = session.session_id
        source_mode = session.mode
        if cycle is None:
            status = "waiting"
        elif triplet is None or triplet.status != "ok":
            status = "degraded"
        else:
            status = "ready"

    return AgentReading(
        status=status,
        cycle_status=cycle.status if cycle is not None else None,
        focus=request.focus,
        session_id=session_id,
        source_mode=source_mode,
        stream_state=stream_state,
        provider=provider_health.provider if provider_health is not None else None,
        provider_health=provider_health,
        real_model_calls=model_calls,
        latest_triplet=triplet,
        council_cycle=cycle,
        usage=usage,
        response_latency_ms=round((perf_counter() - started) * 1000.0, 3),
        generated_at=datetime.now(UTC),
        truth_boundary=list(TRUTH_BOUNDARY),
    )


@router.get("/latest", response_model=AgentReading)
async def latest_agent_reading() -> AgentReading:
    """Return immediately with the latest audited reading, if one exists."""
    return await _query(AgentQueryRequest(wait_timeout_s=0.0))


@router.post("/query", response_model=AgentReading)
async def query_agent_reading(request: AgentQueryRequest) -> AgentReading:
    """Wait briefly for a completed cycle and return one evaluator-friendly response."""
    return await _query(request)


async def _invoke_real_council(request: AgentInvokeRequest) -> AgentReading:
    started = perf_counter()
    deadline = asyncio.get_running_loop().time() + request.evidence_wait_timeout_s
    session = get_hub().session
    packet = session.latest_inference_evidence if session is not None else None
    while packet is None and asyncio.get_running_loop().time() < deadline:
        await asyncio.sleep(0.05)
        session = get_hub().session
        packet = session.latest_inference_evidence if session is not None else None
    if session is None or packet is None:
        raise HTTPException(
            status_code=503,
            detail="no integrity-verified evidence is ready for Agent invocation",
        )
    captured_state = str(session.status()["state"])
    try:
        run = await get_verified_runner().run(packet)
    except RealProviderUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except RealProviderIncomplete as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    calls = sum(record.status == "ok" for record in run.detail.calls)
    # Reaching this point means the bounded provider run completed and passed
    # the verified-runner gates. Semantic uncertainty belongs to cycle_status;
    # it must not make a technically successful invocation look like a failed
    # transport or provider call.
    status: Literal["ready", "waiting", "degraded", "unavailable"] = "ready"
    return AgentReading(
        status=status,
        cycle_status=run.detail.status,
        focus=request.focus,
        session_id=run.packet.session_id,
        source_mode=run.packet.source_manifest.source_mode,
        stream_state=captured_state,
        provider=run.provider_health.provider,
        provider_health=run.provider_health,
        real_model_calls=calls,
        latest_triplet=run.packet.signals,
        council_cycle=run.detail,
        usage=run.usage,
        response_latency_ms=round((perf_counter() - started) * 1000.0, 3),
        generated_at=datetime.now(UTC),
        truth_boundary=list(TRUTH_BOUNDARY),
    )


@router.post("/invoke", response_model=AgentReading)
async def invoke_agent(request: AgentInvokeRequest | None = None) -> AgentReading:
    """Run one bounded real-provider Council cycle and return it synchronously.

    The successful result is cached process-wide, so repeated evaluator calls
    do not repeatedly spend tokens. The continuously looping Replay remains a
    deterministic sensing presentation and never triggers model calls itself.
    """
    return await _invoke_real_council(request or AgentInvokeRequest())
