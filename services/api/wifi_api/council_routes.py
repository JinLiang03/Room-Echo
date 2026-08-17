"""Council API: cycle detail, claims, challenges, rejections, health, usage."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from wifi_contracts import (
    AgentChallenge,
    AgentClaim,
    CouncilCycleDetail,
    CouncilUsageSummary,
    PolicyRejection,
    ProviderHealth,
)
from wifi_council.runtime import CouncilRuntime, get_runtime

from .stream import get_hub

router = APIRouter(prefix="/council", tags=["council"])


def _active_runtime() -> CouncilRuntime:
    """Use the runtime that produced the active stream before the fallback singleton."""
    session = get_hub().session
    if session is not None and session.council_runtime is not None:
        return session.council_runtime
    return get_runtime()


@router.get("/health", response_model=list[ProviderHealth])
def council_health() -> list[ProviderHealth]:
    return _active_runtime().health()


@router.get("/usage", response_model=CouncilUsageSummary)
def council_usage() -> CouncilUsageSummary:
    return _active_runtime().store.usage_summary()


@router.get("/cycles", response_model=list[str])
def council_cycles() -> list[str]:
    return _active_runtime().store.cycle_ids()


def _cycle_or_404(cycle_id: str) -> CouncilCycleDetail:
    detail = _active_runtime().store.get(cycle_id)
    if detail is None:
        raise HTTPException(status_code=404, detail=f"unknown cycle {cycle_id}")
    return detail


@router.get("/cycles/{cycle_id}", response_model=CouncilCycleDetail)
def council_cycle(cycle_id: str) -> CouncilCycleDetail:
    return _cycle_or_404(cycle_id)


@router.get("/cycles/{cycle_id}/claims", response_model=list[AgentClaim])
def council_claims(cycle_id: str) -> list[AgentClaim]:
    return _cycle_or_404(cycle_id).claims


@router.get("/cycles/{cycle_id}/challenges", response_model=list[AgentChallenge])
def council_challenges(cycle_id: str) -> list[AgentChallenge]:
    return _cycle_or_404(cycle_id).challenges


@router.get("/cycles/{cycle_id}/rejections", response_model=list[PolicyRejection])
def council_rejections(cycle_id: str) -> list[PolicyRejection]:
    return _cycle_or_404(cycle_id).rejections
