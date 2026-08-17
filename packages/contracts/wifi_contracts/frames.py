"""Source manifests and normalized CSI frames."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

from .base import HASH_PATTERN, SCHEMA_BASE, SourceMode


class CsiQuality(BaseModel):
    model_config = ConfigDict(extra="forbid")

    parse_ok: bool
    sequence_gap: int = Field(ge=0)
    timestamp_monotonic: bool
    notes: list[str] = Field(default_factory=list)


class SourceManifest(BaseModel):
    """Identifies where a session's data came from and under what topology."""

    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "$id": f"{SCHEMA_BASE}/source_manifest.schema.json",
            "title": "SourceManifest",
        },
    )

    schema_version: Literal["wifi-source.v1"] = "wifi-source.v1"
    session_id: str = Field(min_length=1)
    source_mode: SourceMode
    session_started_at: datetime
    link_ids: list[str] = Field(min_length=1)
    firmware_versions: dict[str, str] = Field(default_factory=dict)
    topology_hash: str = Field(pattern=HASH_PATTERN)
    replay_ref: str | None = None


class NormalizedCsiFrame(BaseModel):
    """A validated CSI frame in host time; the raw fact consumed by the pipeline."""

    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "$id": f"{SCHEMA_BASE}/csi_frame.schema.json",
            "title": "NormalizedCsiFrame",
        },
    )

    schema_version: Literal["1.0.0"] = "1.0.0"
    session_id: str = Field(min_length=1)
    source_mode: SourceMode
    link_id: str = Field(min_length=1)
    rx_id: str = Field(min_length=1)
    tx_id_hash: str | None = None
    seq: int = Field(ge=0)
    device_ts_us: int = Field(ge=0)
    host_ts_ns: int = Field(ge=0)
    channel: int = Field(ge=1, le=196)
    bandwidth_mhz: Literal[20, 40]
    rssi_dbm: float
    noise_floor_dbm: float
    rate: int | None = None
    secondary_channel: int | None = None
    ltf_mode: str | None = None
    first_word_invalid: bool = False
    csi_iq: list[Annotated[int, Field(ge=-128, le=127)]] = Field(min_length=2)
    quality: CsiQuality
