"""Source health: link state and monotonic counters for one session."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from .base import SCHEMA_BASE, SourceMode


class SourceHealth(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "$id": f"{SCHEMA_BASE}/source_health.schema.json",
            "title": "SourceHealth",
        },
    )

    schema_version: Literal["source-health.v1"] = "source-health.v1"
    session_id: str = Field(min_length=1)
    source_mode: SourceMode
    status: Literal["ok", "degraded", "stale", "error"]
    active_links: list[str] = Field(default_factory=list)
    degraded_links: list[str] = Field(default_factory=list)
    dropped_links: list[str] = Field(default_factory=list)
    counters: dict[str, int] = Field(default_factory=dict)
    epoch: int = Field(default=0, ge=0)
    updated_at: datetime
