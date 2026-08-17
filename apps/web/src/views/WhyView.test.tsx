import { describe, expect, it } from "vitest";
import { initialState } from "../lib/state";
import type { CycleView, StreamState } from "../lib/types";
import { renderWithStream } from "../test-utils";
import { WhyView } from "./WhyView";

function cycle(
  cycleId: string,
  status: "supported" | "ambiguous" | "unavailable",
  headline: string,
): CycleView {
  const confidence = status === "unavailable" ? 0 : 0.6;
  return {
    cycleId,
    claims: [],
    challenges: [],
    rejections: [],
    result: {
      schema_version: "council-result.v1",
      cycle_id: cycleId,
      evidence_hash: `sha256:${"a".repeat(64)}`,
      status,
      headline,
      summary: headline,
      sensor_confidence_cap: confidence,
      model_support: confidence,
      display_confidence: confidence,
      interpretation_agreement: {
        participants: 1,
        supporting: status === "unavailable" ? 0 : 1,
        contradicting: 0,
        unresolved_challenges: 0,
        agreement_ratio: status === "unavailable" ? 0 : 1,
      },
      provenance: {
        contracts_version: "1.0.0",
        features_version: "features-v2",
        calibration_profile_id: "demo_room_v1",
        policy_version: "policy-v1",
        generated_at: "2026-08-08T14:00:00Z",
      },
    },
  };
}

function stateWithCycles(cycles: CycleView[]): StreamState {
  const state = initialState();
  return {
    ...state,
    council: {
      cycles: Object.fromEntries(cycles.map((item) => [item.cycleId, item])),
      order: cycles.map((item) => item.cycleId),
      discussionUnavailable: false,
    },
  };
}

describe("WhyView", () => {
  it("keeps the latest interpretable result visible when a stale cycle ends the stream", () => {
    const state = stateWithCycles([
      cycle("cycle-0001", "supported", "最近一次可解释结果"),
      cycle("cycle-0002", "unavailable", "质量门未通过,无推理"),
    ]);
    const { container, getByText } = renderWithStream(<WhyView />, state);

    expect(container.querySelector(".why-summary p")?.textContent).toBe(
      "最近一次可解释结果",
    );
    expect(getByText("此刻证据不足 · 回看最近一次可解释周期")).toBeDefined();
  });

  it("shows unavailable honestly when no interpretable cycle exists", () => {
    const state = stateWithCycles([
      cycle("cycle-0001", "unavailable", "质量门未通过,无推理"),
    ]);
    const { container } = renderWithStream(<WhyView />, state);

    expect(container.querySelector(".why-summary p")?.textContent).toBe(
      "质量门未通过,无推理",
    );
  });
});
