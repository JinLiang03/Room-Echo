"""Ordered registry of contract models used by schema/type generators."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, TypeAdapter

from .council import (
    AgentChallenge,
    AgentClaim,
    CouncilCallRecord,
    CouncilCycleDetail,
    CouncilResult,
    CouncilUsageSummary,
    PolicyRejection,
    ProviderHealth,
)
from .events import WebSocketEnvelope
from .evidence import EvidencePacket
from .frames import NormalizedCsiFrame, SourceManifest
from .health import SourceHealth
from .signals import FeatureWindow, SignalTriplet

CONTRACT_SCHEMAS: list[tuple[str, type[BaseModel]]] = [
    ("source_manifest", SourceManifest),
    ("csi_frame", NormalizedCsiFrame),
    ("feature_window", FeatureWindow),
    ("signal_triplet", SignalTriplet),
    ("evidence_packet", EvidencePacket),
    ("agent_claim", AgentClaim),
    ("agent_challenge", AgentChallenge),
    ("council_result", CouncilResult),
    ("policy_rejection", PolicyRejection),
    ("council_call_record", CouncilCallRecord),
    ("provider_health", ProviderHealth),
    ("council_usage_summary", CouncilUsageSummary),
    ("council_cycle_detail", CouncilCycleDetail),
    ("ws_event", WebSocketEnvelope),
    ("source_health", SourceHealth),
]


def schema_for(name: str) -> dict[str, Any]:
    """Return the JSON Schema for a registered contract by file-stem name."""
    for registry_name, model in CONTRACT_SCHEMAS:
        if registry_name == name:
            return TypeAdapter(model).json_schema()
    raise KeyError(f"unknown contract schema: {name}")
