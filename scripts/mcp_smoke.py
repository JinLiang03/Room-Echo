#!/usr/bin/env python3
"""Verify an installed WiFi Spatial Council MCP endpoint with the official client."""

from __future__ import annotations

import argparse
import asyncio
import json
from typing import Any

from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client

EXPECTED_TOOLS = {
    "get_system_health",
    "invoke_room_echo",
}

TOOL_CALLS: tuple[tuple[str, dict[str, Any]], ...] = (
    ("get_system_health", {}),
    (
        "invoke_room_echo",
        {
            "focus": "limitations",
            "evidence_wait_timeout_s": 30.0,
        },
    ),
)


def _validate_common(name: str, payload: dict[str, Any]) -> None:
    if payload.get("schema_version") != "mcp-tool-response.v1":
        raise RuntimeError(f"{name} returned an unexpected response schema")
    if not payload.get("truth_boundary"):
        raise RuntimeError(f"{name} omitted its truth boundary")
    provenance = payload.get("provider_provenance")
    if not isinstance(provenance, dict):
        raise RuntimeError(f"{name} omitted provider provenance")
    quality = payload.get("quality")
    if not isinstance(quality, dict) or quality.get("status") not in {
        "ok",
        "degraded",
        "unknown",
    }:
        raise RuntimeError(f"{name} returned invalid quality metadata")


def _validate_tool(
    name: str,
    payload: dict[str, Any],
    expected_provider: str,
) -> dict[str, Any]:
    _validate_common(name, payload)
    provenance = payload["provider_provenance"]
    summary: dict[str, Any] = {
        "quality": payload["quality"]["status"],
        "session_id": payload.get("session_id"),
        "provider": provenance.get("council_provider"),
        "real_model_calls": provenance.get("real_model_calls", 0),
    }
    if name == "get_system_health":
        if not isinstance(payload.get("public_replay_read_only"), bool):
            raise RuntimeError("get_system_health omitted the read-only capability")
        summary["status"] = payload.get("status")
        summary["public_replay_read_only"] = payload["public_replay_read_only"]
    elif name == "invoke_room_echo":
        reading = payload.get("reading")
        if not isinstance(reading, dict) or reading.get("council_cycle") is None:
            raise RuntimeError("invoke_room_echo returned no completed Council cycle")
        if payload.get("status") != "ready" or reading.get("status") != "ready":
            raise RuntimeError(
                "invoke_room_echo completed technically but did not expose status=ready"
            )
        if reading.get("provider") != expected_provider:
            raise RuntimeError("invoke_room_echo was not backed by the real provider")
        if int(reading.get("real_model_calls", 0)) < 7:
            raise RuntimeError("invoke_room_echo did not complete the full Council")
        cycle = reading["council_cycle"]
        cycle_status = cycle.get("status")
        if payload.get("cycle_status") != cycle_status or reading.get("cycle_status") != cycle_status:
            raise RuntimeError("invoke_room_echo did not separate technical and semantic status")
        claims = cycle.get("claims") or []
        presentations = {
            str(claim.get("role")): claim.get("presentation")
            for claim in claims
            if isinstance(claim, dict) and isinstance(claim.get("presentation"), dict)
        }
        expected_presentations = {
            "architecture",
            "biota",
            "feng_shui",
            "psyche",
            "soundscape",
        }
        if set(presentations) != expected_presentations:
            raise RuntimeError("invoke_room_echo omitted a specialist presentation")
        sound_presentation = presentations["soundscape"]
        if not isinstance(sound_presentation, dict):
            raise RuntimeError("soundscape presentation has an invalid shape")
        if sound_presentation.get("analysis") is not None:
            raise RuntimeError("soundscape presentation unexpectedly exposed prose")
        challenges = cycle.get("challenges") or []
        if not challenges or any(
            not isinstance(challenge, dict)
            or not isinstance(challenge.get("assessment"), dict)
            for challenge in challenges
        ):
            raise RuntimeError("invoke_room_echo omitted skeptic assessments")
        result = cycle.get("result")
        if not isinstance(result, dict):
            raise RuntimeError("invoke_room_echo omitted the Council result")
        sound_motion = result.get("sound_motion")
        life_interaction = result.get("life_interaction")
        if not isinstance(sound_motion, dict) or set(sound_motion) != {
            "schema_version",
            "rhythm",
            "pitch",
            "distance",
            "thickness",
            "synchrony",
        }:
            raise RuntimeError("invoke_room_echo omitted the five-axis sound motion")
        if not isinstance(life_interaction, dict) or not str(
            life_interaction.get("message", "")
        ).startswith("我"):
            raise RuntimeError("invoke_room_echo omitted first-person life interaction")
        summary["status"] = reading.get("status")
        summary["cycle_status"] = cycle_status
        summary["provider"] = reading.get("provider")
        summary["presentation_roles"] = sorted(presentations)
        summary["sound_axes"] = {
            key: sound_motion[key]
            for key in ("rhythm", "pitch", "distance", "thickness", "synchrony")
        }
        summary["skeptic_assessments"] = len(challenges)
        summary["life_state"] = life_interaction.get("state")
    return summary


async def smoke(url: str, expected_provider: str = "openai") -> dict[str, Any]:
    async with (
        streamable_http_client(url, terminate_on_close=False) as (
            read_stream,
            write_stream,
            _get_session_id,
        ),
        ClientSession(read_stream, write_stream) as client,
    ):
        initialized = await client.initialize()
        listed = await client.list_tools()
        names = {tool.name for tool in listed.tools}
        missing = EXPECTED_TOOLS - names
        if missing:
            raise RuntimeError(f"MCP tools missing: {sorted(missing)}")
        annotations = {tool.name: tool.annotations for tool in listed.tools}
        health_annotations = annotations["get_system_health"]
        invoke_annotations = annotations["invoke_room_echo"]
        if (
            health_annotations is None
            or health_annotations.readOnlyHint is not True
            or health_annotations.destructiveHint is not False
        ):
            raise RuntimeError("get_system_health annotations are unsafe")
        if (
            invoke_annotations is None
            or invoke_annotations.readOnlyHint is not False
            or invoke_annotations.destructiveHint is not False
            or invoke_annotations.openWorldHint is not True
        ):
            raise RuntimeError("invoke_room_echo annotations omit its provider call")
        checks: dict[str, dict[str, Any]] = {}
        for name, arguments in TOOL_CALLS:
            result = await asyncio.wait_for(
                client.call_tool(name, arguments),
                timeout=180.0,
            )
            if result.isError:
                raise RuntimeError(f"{name} returned an MCP error")
            if result.structuredContent is None:
                raise RuntimeError(f"{name} returned no structured content")
            checks[name] = _validate_tool(
                name,
                dict(result.structuredContent),
                expected_provider,
            )
        return {
            "server": initialized.serverInfo.name,
            "protocol_version": initialized.protocolVersion,
            "tools": sorted(names),
            "checks": checks,
        }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "url",
        nargs="?",
        default="http://127.0.0.1:8000/mcp/",
        help="Streamable HTTP MCP endpoint",
    )
    parser.add_argument(
        "--provider",
        choices=("openai", "deepseek"),
        default="openai",
        help="Expected real-provider provenance for invoke_room_echo",
    )
    args = parser.parse_args()
    print(
        json.dumps(
            asyncio.run(smoke(args.url, args.provider)),
            indent=2,
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
