"""Deterministic safe-action projection from sealed evidence and Policy state."""

from __future__ import annotations

import math
from datetime import datetime
from typing import Literal

from wifi_contracts import AgentActionDecision, EvidencePacket

CouncilStatus = Literal["supported", "ambiguous", "unavailable"]


def _bounded_confidence(value: float, cap: float) -> float:
    if not math.isfinite(value):
        return 0.0
    return round(min(max(value, 0.0), cap), 6)


def build_agent_action_decision(
    packet: EvidencePacket,
    *,
    status: CouncilStatus,
    decision_confidence: float,
    decided_at: datetime,
) -> AgentActionDecision:
    """Project one action without reading provider prose or agent agreement.

    Only the sealed packet plus the deterministic Policy status/confidence can
    affect this projection. No caller may pass a provider-authored action.
    """

    mode = packet.source_manifest.source_mode
    sensor_cap = packet.signals.sensor_confidence_cap
    confidence = _bounded_confidence(decision_confidence, sensor_cap)
    refs = [
        f"evidence://{packet.evidence_hash}/quality/overall_status",
        f"evidence://{packet.evidence_hash}/sensor/sensor_confidence_cap",
    ]
    common = {
        "schema_version": "agent-action-decision.v1",
        "decision_id": f"action-{packet.session_id}-{packet.cycle_id}",
        "session_id": packet.session_id,
        "cycle_id": packet.cycle_id,
        "evidence_hash": packet.evidence_hash,
        "decided_at": decided_at,
        "source_mode": mode,
        "quality_status": packet.signals.status,
        "quality_flags": list(packet.quality.quality_flags),
        "evidence_refs": refs,
        "sensor_confidence_cap": sensor_cap,
    }

    if not packet.verify_integrity():
        return AgentActionDecision.model_validate(
            {
                **common,
                "action_type": "stay_silent",
                "execution_status": "withheld",
                "target": "none",
                "reason_code": "evidence_integrity_failed",
                "explanation": "证据封存校验未通过,保持静默且不触发外部设备。",
                "decision_confidence": 0.0,
            }
        )

    if (
        packet.source_manifest.session_id != packet.session_id
        or packet.signals.session_id != packet.session_id
        or packet.signals.source_mode != mode
    ):
        return AgentActionDecision.model_validate(
            {
                **common,
                "action_type": "stay_silent",
                "execution_status": "withheld",
                "target": "none",
                "reason_code": "source_contract_mismatch",
                "explanation": "来源契约不一致,保持静默并等待新的完整快照。",
                "decision_confidence": 0.0,
            }
        )

    if mode == "live":
        return AgentActionDecision.model_validate(
            {
                **common,
                "action_type": "stay_silent",
                "execution_status": "withheld",
                "target": "none",
                "reason_code": "no_actuator_adapter",
                "explanation": "实时来源尚未配置执行器适配器,本周期行动被明确保留。",
                "decision_confidence": confidence,
            }
        )

    if (
        status == "unavailable"
        or packet.signals.status in ("insufficient_signal", "uncalibrated")
        or confidence <= 0.0
    ):
        return AgentActionDecision.model_validate(
            {
                **common,
                "action_type": "stay_silent",
                "execution_status": "withheld",
                "target": "none",
                "reason_code": "insufficient_evidence",
                "explanation": "当前代理证据不足,保持静默并等待下一份完整快照。",
                "decision_confidence": 0.0,
            }
        )

    if (
        status == "ambiguous"
        or packet.signals.status == "degraded"
        or bool(packet.quality.quality_flags)
    ):
        return AgentActionDecision.model_validate(
            {
                **common,
                "action_type": "wait_and_observe",
                "execution_status": "withheld",
                "target": "none",
                "reason_code": "awaiting_validation",
                "explanation": "当前代理解释仍需对照,暂不预览并继续观察新周期。",
                "decision_confidence": confidence,
            }
        )

    return AgentActionDecision.model_validate(
        {
            **common,
            "action_type": "ambient_light_preview",
            "execution_status": "simulated_preview",
            "target": "inference_field_preview",
            "reason_code": "simulated_source_preview",
            "explanation": "仅在推断场中模拟环境光反应,不触发外部设备。",
            "decision_confidence": confidence,
        }
    )
