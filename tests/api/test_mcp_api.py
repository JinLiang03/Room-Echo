"""Protocol-level integration tests for the read-only Streamable HTTP MCP."""

from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx
import pytest
from fastapi import FastAPI
from fastapi.responses import RedirectResponse
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client
from wifi_api.mcp_server import create_mcp_server
from wifi_api.real_provider import reset_verified_runner_for_testing
from wifi_api.stream import StreamSession, reset_hub_for_testing
from wifi_contracts import ProviderHealth
from wifi_council.config import CouncilConfig
from wifi_council.provider import MockAgentProvider

ROOT = Path(__file__).resolve().parents[2]
WALK_THROUGH = ROOT / "data" / "fixtures" / "walk_through"


class _TestOpenAIProvider(MockAgentProvider):
    name = "openai"

    def __init__(self, config: CouncilConfig) -> None:
        super().__init__(config)
        self.model = "test-openai-model"

    def health(self) -> ProviderHealth:
        return ProviderHealth(
            schema_version="provider-health.v1",
            provider="openai",
            status="ok",
            model=self.model,
            detail="configured test provider",
            checked_at=datetime.now(UTC),
        )


def _structured(result: Any) -> dict[str, Any]:
    assert result.isError is not True
    assert result.structuredContent is not None
    return dict(result.structuredContent)


def test_mcp_initialize_list_and_call_read_only_tools(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Exercise the official client handshake through the mounted ASGI app."""
    monkeypatch.setenv("PUBLIC_REPLAY", "1")
    monkeypatch.setenv("PUBLIC_OPENAI_INVOKE", "1")
    reset_verified_runner_for_testing(_TestOpenAIProvider)
    hub = reset_hub_for_testing()
    session = StreamSession(
        mode="replay",
        bundle_root=WALK_THROUGH,
        paced=False,
        event_log_dir=tmp_path,
    )
    hub.attach_session(session)
    test_mcp_server = create_mcp_server()
    test_mcp_app = FastAPI()

    @test_mcp_app.api_route("/mcp", methods=["GET", "POST", "DELETE"])
    def mcp_canonical_redirect() -> RedirectResponse:
        return RedirectResponse(url="/mcp/", status_code=307)

    test_mcp_app.mount("/mcp", test_mcp_server.streamable_http_app())

    async def run() -> tuple[set[str], list[dict[str, Any]]]:
        session.start()
        try:
            deadline = asyncio.get_running_loop().time() + 60.0
            while _latest_cycle() is None:
                if session.status()["error"]:
                    raise AssertionError(f"stream failed: {session.status()}")
                if asyncio.get_running_loop().time() > deadline:
                    raise AssertionError(f"council result timed out: {session.status()}")
                await asyncio.sleep(0.01)

            transport = httpx.ASGITransport(app=test_mcp_app)
            async with (
                test_mcp_server.session_manager.run(),
                httpx.AsyncClient(
                    transport=transport,
                    base_url="http://localhost",
                    follow_redirects=True,
                ) as http_client,
                streamable_http_client(
                    "http://localhost/mcp",
                    http_client=http_client,
                    terminate_on_close=False,
                ) as (read_stream, write_stream, _get_session_id),
                ClientSession(read_stream, write_stream) as client,
            ):
                redirect = await http_client.post(
                    "/mcp",
                    json={},
                    follow_redirects=False,
                )
                assert redirect.status_code == 307
                assert redirect.headers["location"] == "/mcp/"

                initialized = await client.initialize()
                assert initialized.serverInfo.name == "WiFi Spatial Council"

                listed = await client.list_tools()
                names = {tool.name for tool in listed.tools}
                annotations = {tool.name: tool.annotations for tool in listed.tools}
                assert annotations["get_system_health"].readOnlyHint is True
                assert annotations["get_system_health"].openWorldHint is False
                assert annotations["invoke_room_echo"].readOnlyHint is False
                assert annotations["invoke_room_echo"].destructiveHint is False
                assert annotations["invoke_room_echo"].openWorldHint is True

                results = [
                    _structured(await client.call_tool("get_system_health")),
                    _structured(
                        await client.call_tool(
                            "invoke_room_echo",
                            {
                                "focus": "limitations",
                                "evidence_wait_timeout_s": 15.0,
                            },
                        )
                    ),
                ]
            return names, results
        finally:
            await session.stop()

    def _latest_cycle() -> Any:
        runtime = session.council_runtime
        return runtime.store.current if runtime is not None else None

    try:
        names, results = asyncio.run(run())
    finally:
        reset_verified_runner_for_testing()
        reset_hub_for_testing()

    assert names == {
        "get_system_health",
        "invoke_room_echo",
    }
    assert all(result["schema_version"] == "mcp-tool-response.v1" for result in results)
    assert all(result["truth_boundary"] for result in results)
    assert all("provider_provenance" in result for result in results)
    assert results[0]["public_replay_read_only"] is True
    assert results[1]["status"] == "ready"
    assert results[1]["cycle_status"] == results[1]["reading"]["cycle_status"]
    assert results[1]["reading"]["status"] == "ready"
    assert results[1]["cycle_status"] == results[1]["reading"]["council_cycle"]["status"]
    assert results[1]["reading"]["provider"] == "openai"
    assert results[1]["provider_provenance"]["real_model_calls"] >= 7
    assert results[1]["reading"]["council_cycle"]["result"] is not None

    serialized = json.dumps(results, ensure_ascii=False)
    for forbidden in (
        "OPENAI_API_KEY",
        "sk-",
        "/" + "Users/",
        "/" + "home/",
        "raw.csi.zst",
        "manifest.json",
    ):
        assert forbidden not in serialized
