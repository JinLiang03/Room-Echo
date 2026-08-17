import { describe, expect, it } from "vitest";
import { themeForAgentResult } from "./agent-visual-theme";
import type { CouncilResult } from "./types";
import { testActionDecision } from "../test-fixtures";

function resultWithEffect(
  effect: NonNullable<CouncilResult["life_interaction"]>["effect"],
): CouncilResult {
  return {
    cycle_id: "cycle-theme",
    evidence_hash: "sha256:theme",
    status: "supported",
    headline: "可用",
    summary: "视觉主题测试",
    accepted_claim_ids: [],
    unresolved_challenge_ids: [],
    alternatives: [],
    limitations: [],
    sensor_confidence_cap: 0.8,
    model_support: 0.7,
    display_confidence: 0.7,
    interpretation_agreement: {
      participants: 7,
      supporting: 6,
      contradicting: 0,
      unresolved_challenges: 0,
      agreement_ratio: 0.86,
    },
    visual_parameters: {},
    audio_parameters: {},
    continuity: null,
    sound_motion: null,
    life_interaction: {
      state: "expanding",
      state_label: "正在展开",
      message: "视觉测试",
      wish: "继续观察",
      effect,
    },
    action_decision: testActionDecision({
      cycleId: "cycle-theme",
      evidenceHash: "sha256:theme",
      sensorCap: 0.8,
    }),
    provenance: {
      contracts_version: "test",
      features_version: "test",
      calibration_profile_id: "test",
      policy_version: "test",
      generated_at: "2026-01-01T00:00:00Z",
    },
  };
}

describe("agent visual theme", () => {
  it("maps Fusion effects to presentation-only spatial metaphors", () => {
    expect(themeForAgentResult(resultWithEffect("expand"), "abstract_presence")).toBe(
      "lounge",
    );
    expect(themeForAgentResult(resultWithEffect("startle"), "abstract_presence")).toBe(
      "floor_lamp",
    );
    expect(themeForAgentResult(resultWithEffect("contract"), "abstract_presence")).toBe(
      "floorplan",
    );
  });

  it("keeps the fallback when no approved Fusion result exists", () => {
    expect(themeForAgentResult(null, "sofa")).toBe("sofa");
    expect(themeForAgentResult({ ...resultWithEffect("expand"), status: "unavailable" }, "sofa")).toBe(
      "sofa",
    );
  });
});
