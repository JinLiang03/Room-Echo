"""Sealed evidence packets: the only object agents may consume."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from .base import HASH_PATTERN, SCHEMA_BASE
from .frames import SourceManifest
from .signals import LinkFeatures, SignalTriplet


class WindowSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    window_id: str = Field(min_length=1)
    start_ns: int = Field(ge=0)
    end_ns: int = Field(ge=0)
    stride_ms: int = Field(ge=1)
    links: dict[str, LinkFeatures]
    paired_packet_coverage: float = Field(ge=0, le=1)


class TopologySummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    topology_hash: str = Field(pattern=HASH_PATTERN)
    link_ids: list[str] = Field(min_length=1)
    degraded_links: list[str] = Field(default_factory=list)
    depth_output_allowed: bool


class CalibrationSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    calibration_profile_id: str = Field(min_length=1)
    profile_hash: str = Field(pattern=HASH_PATTERN)
    calibrated_at: datetime
    room_conditions: str | None = None


class QualitySummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    overall_status: Literal["ok", "degraded", "insufficient_signal", "uncalibrated"]
    packet_coverage: float = Field(ge=0, le=1)
    link_health: dict[str, Literal["ok", "degraded", "stale", "error"]]
    quality_flags: list[str] = Field(default_factory=list)


class EvidenceValue(BaseModel):
    model_config = ConfigDict(extra="forbid")

    path: str = Field(min_length=1)
    value: float | int | str | bool
    unit: str | None = None
    description: str | None = None


class EvidencePacket(BaseModel):
    """One sealed snapshot of a single analysis cycle; immutable once hashed."""

    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "$id": f"{SCHEMA_BASE}/evidence_packet.schema.json",
            "title": "EvidencePacket",
        },
    )

    schema_version: Literal["wifi-evidence.v1"] = "wifi-evidence.v1"
    session_id: str = Field(min_length=1)
    cycle_id: str = Field(min_length=1)
    sequence: int = Field(ge=0)
    captured_at: datetime
    source_manifest: SourceManifest
    window_summary: WindowSummary
    topology: TopologySummary
    calibration: CalibrationSummary
    quality: QualitySummary
    signals: SignalTriplet
    evidence_index: dict[str, EvidenceValue]
    raw_ref: str = Field(min_length=1)
    evidence_hash: str = Field(pattern=HASH_PATTERN)

    def canonical_payload(self) -> str:
        data = self.model_dump(mode="json", exclude={"evidence_hash"})
        return json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False)

    def compute_evidence_hash(self) -> str:
        digest = hashlib.sha256(self.canonical_payload().encode("utf-8")).hexdigest()
        return f"sha256:{digest}"

    def verify_integrity(self) -> bool:
        """True when the stored hash still matches the payload (seal check)."""
        return self.evidence_hash == self.compute_evidence_hash()

    @classmethod
    def create(cls, **values: Any) -> EvidencePacket:
        """Construct a sealed packet with the hash computed from the payload."""
        values.setdefault("schema_version", "wifi-evidence.v1")
        values["evidence_hash"] = "sha256:" + "0" * 64
        packet = cls(**values)
        packet.evidence_hash = packet.compute_evidence_hash()
        return packet
