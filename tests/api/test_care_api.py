"""Read-only API coverage for the explicit care simulation."""

from __future__ import annotations

import asyncio

import httpx
import pytest
from wifi_api.app import app


@pytest.mark.parametrize(
    "moment,index",
    [
        ("routine", 0),
        ("bathroom_timeout", 1),
        ("fall_drill", 2),
        ("pet_night", 3),
    ],
)
def test_care_scenario_endpoint_selects_requested_moment(
    moment: str,
    index: int,
) -> None:
    async def run() -> httpx.Response:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://test",
        ) as client:
            return await client.get("/api/care/scenario", params={"moment": moment})

    response = asyncio.run(run())
    assert response.status_code == 200
    payload = response.json()
    assert payload["schema_version"] == "simulated-care-scenario.v2"
    assert payload["simulation_only"] is True
    assert payload["source_mode"] == "mock"
    assert payload["device_execution_enabled"] is False
    assert payload["selected_moment"] == moment
    assert payload["current_index"] == index
    assert payload["moments"][index]["moment"] == moment
    assert len(payload["moments"][index]["suggestions"]) == 4
    selected = payload["moments"][index]
    triplet = selected["evidence_core"]["proxy_triplet"]
    assert triplet["session_id"] == payload["scenario_id"]
    assert triplet["source_mode"] == payload["source_mode"] == "mock"
    assert triplet["ended_at"] == selected["occurred_at"]
    assert triplet["sensor_confidence_cap"] == selected["sensor_confidence_cap"]
    assert triplet["window_id"] in triplet["evidence_refs"][0]
    assert selected["interpretation_status"] == "supported"


def test_care_scenario_endpoint_rejects_unknown_moment() -> None:
    async def run() -> httpx.Response:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://test",
        ) as client:
            return await client.get(
                "/api/care/scenario",
                params={"moment": "camera_fall_detection"},
            )

    response = asyncio.run(run())
    assert response.status_code == 422
