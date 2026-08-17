"""Read-only endpoint for the explicitly simulated ageing-in-place demo."""

from __future__ import annotations

from fastapi import APIRouter
from wifi_contracts import (
    CareMomentKey,
    SimulatedCareScenario,
    build_simulated_care_scenario,
)

router = APIRouter(prefix="/api/care", tags=["care-simulation"])


@router.get("/scenario", response_model=SimulatedCareScenario)
def simulated_care_scenario(
    moment: CareMomentKey = "bathroom_timeout",
) -> SimulatedCareScenario:
    """Return one deterministic fictional day with the requested UI moment.

    The response itself carries a mandatory simulation marker and truth
    boundary.  It has no route that sends messages or invokes devices.
    """
    return build_simulated_care_scenario(moment)
