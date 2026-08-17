#!/usr/bin/env python3
"""Generate TypeScript contract types from the Pydantic JSON Schemas."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from wifi_contracts.care_fixtures import build_simulated_care_scenario
from wifi_contracts.mock_fixtures import (
    build_agent_action_decisions,
    build_agent_challenges,
    build_agent_claims,
    build_council_cycle_details,
    build_council_results,
    build_evidence_packets,
    build_frames,
    build_policy_rejections,
    build_triplets,
    build_windows,
)
from wifi_contracts.registry import CONTRACT_SCHEMAS, schema_for

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "apps/web/src/generated/contracts.ts"
FIXTURES_OUTPUT = ROOT / "apps/web/src/generated/fixtures.ts"

HEADER = (
    "// GENERATED FILE — do not edit by hand.\n"
    "// Source of truth: packages/contracts/wifi_contracts (Pydantic models).\n"
    "// Regenerate with: uv run python scripts/generate_types.py\n"
    "// Drift check: make verify-contracts\n"
)


def _literal(value: Any) -> str:
    if isinstance(value, str):
        return json.dumps(value, ensure_ascii=False)
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return json.dumps(value)
    raise ValueError(f"unsupported literal value: {value!r}")


def _ref_name(ref: str) -> str:
    return ref.rsplit("/", 1)[-1]


def _wrap(part: str) -> str:
    if any(marker in part for marker in (" | ", " => ", ": ")):
        return f"({part})"
    return part


def _ts_type(schema: dict[str, Any], defs: dict[str, dict[str, Any]]) -> str:
    if "$ref" in schema:
        return _ref_name(schema["$ref"])
    if "const" in schema:
        return _literal(schema["const"])
    if "enum" in schema:
        return " | ".join(_literal(value) for value in schema["enum"])
    if "anyOf" in schema:
        parts = [_ts_type(option, defs) for option in schema["anyOf"]]
        return " | ".join(_wrap(part) for part in parts)
    if "type" in schema:
        types = schema["type"]
        if isinstance(types, list):
            parts = [_ts_type({**schema, "type": kind}, defs) for kind in types]
            return " | ".join(_wrap(part) for part in parts)
        if types == "array":
            items = schema.get("items", {})
            return f"Array<{_ts_type(items, defs)}>"
        if types == "object":
            if "properties" in schema:
                return _inline_object(schema, defs)
            additional = schema.get("additionalProperties", True)
            if additional is True or additional == {}:
                return "Record<string, unknown>"
            if isinstance(additional, dict):
                return f"Record<string, {_ts_type(additional, defs)}>"
            return "Record<string, never>"
        if types in ("integer", "number"):
            return "number"
        if types == "string":
            return "string"
        if types == "boolean":
            return "boolean"
        if types == "null":
            return "null"
        raise ValueError(f"unsupported JSON Schema type: {types!r}")
    raise ValueError(f"unsupported JSON Schema node: {schema!r}")


def _inline_object(schema: dict[str, Any], defs: dict[str, dict[str, Any]]) -> str:
    properties = schema.get("properties", {})
    required = set(schema.get("required", []))
    members = []
    for name, prop_schema in properties.items():
        suffix = "" if name in required else "?"
        members.append(f"{name}{suffix}: {_ts_type(prop_schema, defs)};")
    return "{ " + " ".join(members) + " }"


def _render_def(name: str, schema: dict[str, Any], defs: dict[str, dict[str, Any]]) -> str:
    if "enum" in schema:
        return f"export type {name} = {_ts_type(schema, defs)};"
    if schema.get("type") == "object" and "properties" in schema:
        body = _inline_object(schema, defs)
        return f"export interface {name} {body}"
    return f"export type {name} = {_ts_type(schema, defs)};"


def _render_root(
    fallback_name: str,
    schema: dict[str, Any],
    defs: dict[str, dict[str, Any]],
) -> str:
    title = schema.get("title", fallback_name)
    body = _inline_object(schema, defs)
    return f"export interface {title} {body}"


def render_contracts() -> str:
    lines = [HEADER, ""]
    for name, _model in CONTRACT_SCHEMAS:
        schema = schema_for(name)
        defs = schema.get("$defs", {})
        for def_name in sorted(defs):
            lines.append(_render_def(def_name, defs[def_name], defs))
        if defs:
            lines.append("")
        lines.append(_render_root(name, schema, defs))
        lines.append("")
    return "\n".join(lines)


def render_fixtures() -> str:
    """Emit the mock fixtures as typed TS literals (contextual type checking)."""
    payloads: list[tuple[str, str, list[Any]]] = [
        ("csiFrames", "NormalizedCsiFrame", [frame.model_dump(mode="json") for frame in build_frames()]),
        (
            "featureWindows",
            "FeatureWindow",
            [window.model_dump(mode="json") for window in build_windows()],
        ),
        (
            "signalTriplets",
            "SignalTriplet",
            [triplet.model_dump(mode="json") for triplet in build_triplets()],
        ),
        (
            "evidencePackets",
            "EvidencePacket",
            [packet.model_dump(mode="json") for packet in build_evidence_packets()],
        ),
        (
            "agentClaims",
            "AgentClaim",
            [claim.model_dump(mode="json") for claim in build_agent_claims()],
        ),
        (
            "agentChallenges",
            "AgentChallenge",
            [
                challenge.model_dump(mode="json")
                for challenge in build_agent_challenges()
            ],
        ),
        (
            "agentActionDecisions",
            "AgentActionDecision",
            [
                decision.model_dump(mode="json")
                for decision in build_agent_action_decisions()
            ],
        ),
        (
            "simulatedCareScenarios",
            "SimulatedCareScenario",
            [build_simulated_care_scenario().model_dump(mode="json")],
        ),
        (
            "policyRejections",
            "PolicyRejection",
            [
                rejection.model_dump(mode="json")
                for rejection in build_policy_rejections()
            ],
        ),
        (
            "councilResults",
            "CouncilResult",
            [result.model_dump(mode="json") for result in build_council_results()],
        ),
        (
            "councilCycleDetails",
            "CouncilCycleDetail",
            [
                detail.model_dump(mode="json")
                for detail in build_council_cycle_details()
            ],
        ),
    ]
    lines = [
        "// GENERATED FILE — do not edit by hand.",
        "// Mock fixtures typed against the generated contracts (compile-time check).",
        "// Regenerate with: uv run python scripts/generate_types.py",
        "// Drift check: make verify-contracts",
        "",
        'import type {',
        "  AgentActionDecision,",
        "  AgentChallenge,",
        "  AgentClaim,",
        "  CouncilCycleDetail,",
        "  CouncilResult,",
        "  EvidencePacket,",
        "  FeatureWindow,",
        "  NormalizedCsiFrame,",
        "  PolicyRejection,",
        "  SignalTriplet,",
        "  SimulatedCareScenario,",
        '} from "./contracts";',
        "",
    ]
    for name, type_name, data in payloads:
        lines.append(
            f"export const {name}: {type_name}[] = "
            f"{json.dumps(data, indent=2, ensure_ascii=False)};"
        )
        lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="fail on drift without writing the file",
    )
    args = parser.parse_args()

    outputs = {
        OUTPUT: render_contracts(),
        FIXTURES_OUTPUT: render_fixtures(),
    }
    drifted: list[str] = []
    for path, rendered in outputs.items():
        if args.check:
            if not path.is_file() or path.read_text(encoding="utf-8") != rendered:
                drifted.append(str(path))
        else:
            path.write_text(rendered, encoding="utf-8")

    if args.check and drifted:
        print("TypeScript type drift detected:")
        for path in drifted:
            print(f"- {path}")
        return 1
    action = "Verified" if args.check else "Wrote"
    for path in outputs:
        print(f"{action} TypeScript artifacts in {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
