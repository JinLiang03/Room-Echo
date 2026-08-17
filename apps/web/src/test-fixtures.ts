import type { AgentActionDecision } from "./generated/contracts";

interface ActionDecisionOptions {
  cycleId?: string;
  evidenceHash?: string;
  sensorCap?: number;
  sourceMode?: "mock" | "replay" | "live";
}

/** A contract-complete, UI-only action decision for hand-written tests. */
export function testActionDecision({
  cycleId = "cycle-test",
  evidenceHash = `sha256:${"a".repeat(64)}`,
  sensorCap = 0.8,
  sourceMode = "replay",
}: ActionDecisionOptions = {}): AgentActionDecision {
  const live = sourceMode === "live";
  return {
    schema_version: "agent-action-decision.v1",
    decision_id: `${cycleId}-action`,
    session_id: "session-test",
    cycle_id: cycleId,
    evidence_hash: evidenceHash,
    decided_at: "2026-08-13T00:00:00Z",
    source_mode: sourceMode,
    quality_status: "ok",
    quality_flags: [],
    action_type: live ? "stay_silent" : "ambient_light_preview",
    execution_status: live ? "withheld" : "simulated_preview",
    target: live ? "none" : "inference_field_preview",
    reason_code: live ? "no_actuator_adapter" : "simulated_source_preview",
    explanation: live
      ? "真实设备适配器尚未启用，本轮保持静默。"
      : "仅在推断场中预演低风险环境回应。",
    evidence_refs: [`evidence://${evidenceHash}/signals`],
    decision_confidence: Math.min(0.6, sensorCap),
    sensor_confidence_cap: sensorCap,
  };
}
