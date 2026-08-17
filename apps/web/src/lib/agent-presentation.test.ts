import { describe, expect, it } from "vitest";
import { signalTriplets } from "../generated/fixtures";
import { testActionDecision } from "../test-fixtures";
import { initialState } from "./state";
import type { CouncilResult, SignalTriplet } from "./types";
import { publicAgentPresentation } from "./agent-presentation";

const triplet = signalTriplets[1] as SignalTriplet;

function result(cycleId: string, evidenceHash: string): CouncilResult {
  return {
    schema_version: "council-result.v1",
    cycle_id: cycleId,
    evidence_hash: evidenceHash,
    status: "supported",
    headline: "受限解释完成",
    summary: "当前代理信号可以支持一次模拟回应。",
    sensor_confidence_cap: 0.72,
    model_support: 0.64,
    display_confidence: 0.6,
    interpretation_agreement: {
      participants: 7,
      supporting: 5,
      contradicting: 1,
      unresolved_challenges: 0,
      agreement_ratio: 5 / 7,
    },
    life_interaction: {
      schema_version: "spatial-life-interaction.v1",
      state: "expanding",
      state_label: "空间变化正在展开",
      message: "我观察到可复核的代理变化。",
      wish: "继续观察。",
      effect: "expand",
    },
    action_decision: testActionDecision({
      cycleId,
      evidenceHash,
      sensorCap: 0.72,
    }),
    provenance: {
      contracts_version: "1.0.0",
      features_version: "features-v2",
      calibration_profile_id: "demo_room_v1",
      policy_version: "policy-v1",
      generated_at: "2026-08-13T00:00:00Z",
    },
  };
}

describe("publicAgentPresentation", () => {
  it("projects exactly the newest sealed cycle into one public voice", () => {
    const state = initialState();
    state.connection = "online";
    state.triplet = { ...triplet, window_id: "newer-unsealed" };
    state.council.cycles["cycle-sealed"] = {
      cycleId: "cycle-sealed",
      evidenceHash: "sha256:sealed",
      signalSnapshot: { ...triplet, window_id: "sealed-window" },
      claims: [],
      challenges: [],
      rejections: [],
      result: result("cycle-sealed", "sha256:sealed"),
    };
    state.council.order = ["cycle-sealed"];

    const agent = publicAgentPresentation(state);

    expect(agent.cycleId).toBe("cycle-sealed");
    expect(agent.evidenceHash).toBe("sha256:sealed");
    expect(agent.snapshot?.window_id).toBe("sealed-window");
    expect(agent.phase).toBe("responding");
  });

  it("clears prior conclusions when the stream is stale", () => {
    const state = initialState();
    state.connection = "offline";
    state.stale = true;
    state.triplet = triplet;

    const agent = publicAgentPresentation(state);

    expect(agent.phase).toBe("unknown");
    expect(agent.snapshot).toBeNull();
    expect(agent.result).toBeNull();
    expect(agent.finalConfidence).toBeNull();
  });
});
