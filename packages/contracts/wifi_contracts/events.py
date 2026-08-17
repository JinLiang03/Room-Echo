"""WebSocket envelope shared by the API and the web client."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from .base import SCHEMA_BASE

WsEventType = Literal[
    "session.status",
    "source.health",
    "signal.frame",
    "quality.update",
    "cycle.started",
    "agent.claim",
    "agent.challenge",
    "agent.response",
    "policy.rejection",
    "synthesis.result",
    "render.update",
    "alert",
    "heartbeat",
]


class WebSocketEnvelope(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "$id": f"{SCHEMA_BASE}/ws_event.schema.json",
            "title": "WebSocketEnvelope",
        },
    )

    schema_version: Literal["ws-event.v1"] = "ws-event.v1"
    session_id: str = Field(min_length=1)
    sequence: int = Field(ge=0)
    emitted_at: datetime
    event_type: WsEventType
    payload: dict[str, Any]
