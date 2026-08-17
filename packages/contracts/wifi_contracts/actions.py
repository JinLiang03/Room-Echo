"""Bounded, auditable action decisions derived from sealed evidence."""

from __future__ import annotations

import re
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .base import HASH_PATTERN, SCHEMA_BASE, SourceMode

AgentActionType = Literal[
    "stay_silent",
    "ambient_light_preview",
    "wait_and_observe",
]
ActionExecutionStatus = Literal["simulated_preview", "withheld"]
ActionTarget = Literal["inference_field_preview", "none"]
ActionReasonCode = Literal[
    "simulated_source_preview",
    "awaiting_validation",
    "insufficient_evidence",
    "evidence_integrity_failed",
    "source_contract_mismatch",
    "no_actuator_adapter",
]

_FORBIDDEN_ACTION_INFERENCE = re.compile(
    r"\b(?:night|path|route|fall|routine|person|people)\b|"
    r"夜间|夜晚|深夜|路径|路线|跌倒|摔倒|坠落|作息|日常规律|人员|有人|身份",
    re.IGNORECASE,
)


class AgentActionDecision(BaseModel):
    """One deterministic safe action projection for a Council result.

    The contract deliberately has no ``executed`` state. Mock and Replay may
    expose a clearly labelled UI-only preview; Live is withheld until a real,
    separately validated actuator adapter exists.
    """

    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "$id": f"{SCHEMA_BASE}/agent_action_decision.schema.json",
            "title": "AgentActionDecision",
        },
    )

    schema_version: Literal["agent-action-decision.v1"] = (
        "agent-action-decision.v1"
    )
    decision_id: str = Field(min_length=1)
    session_id: str = Field(min_length=1)
    cycle_id: str = Field(min_length=1)
    evidence_hash: str = Field(pattern=HASH_PATTERN)
    decided_at: datetime
    source_mode: SourceMode
    quality_status: Literal[
        "ok",
        "degraded",
        "insufficient_signal",
        "uncalibrated",
    ]
    quality_flags: list[str] = Field(default_factory=list)
    action_type: AgentActionType
    execution_status: ActionExecutionStatus
    target: ActionTarget
    reason_code: ActionReasonCode
    explanation: str = Field(min_length=1, max_length=240)
    evidence_refs: list[str] = Field(min_length=1)
    decision_confidence: float = Field(ge=0, le=1)
    sensor_confidence_cap: float = Field(ge=0, le=1)

    @model_validator(mode="after")
    def _enforce_action_boundary(self) -> AgentActionDecision:
        if self.decision_confidence > self.sensor_confidence_cap:
            raise ValueError(
                "decision_confidence <= sensor_confidence_cap invariant violated"
            )
        prefix = f"evidence://{self.evidence_hash}/"
        if any(not ref.startswith(prefix) for ref in self.evidence_refs):
            raise ValueError("action evidence refs must bind to the decision evidence_hash")
        if _FORBIDDEN_ACTION_INFERENCE.search(self.explanation):
            raise ValueError(
                "action explanation must not infer night, path, fall, routine, or people"
            )
        if self.source_mode == "live" and self.execution_status != "withheld":
            raise ValueError("live actions must be withheld without an actuator adapter")
        if self.execution_status == "simulated_preview":
            if self.source_mode not in ("mock", "replay"):
                raise ValueError("only Mock or Replay may emit a simulated preview")
            if self.target != "inference_field_preview":
                raise ValueError("simulated previews must target the inference field")
            if self.action_type != "ambient_light_preview":
                raise ValueError("only ambient_light_preview may be simulated")
            if self.reason_code != "simulated_source_preview":
                raise ValueError("simulated previews require simulated_source_preview")
        elif self.target != "none":
            raise ValueError("withheld actions must not have an execution target")
        if (
            self.action_type == "ambient_light_preview"
            and self.execution_status != "simulated_preview"
        ):
            raise ValueError("ambient_light_preview must remain a simulated preview")
        return self
