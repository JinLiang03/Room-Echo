import { render } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { initialState } from "../lib/state";
import type { AgentClaim, StreamState } from "../lib/types";
import { AgentResponseOverlay } from "./AgentResponseOverlay";

describe("AgentResponseOverlay", () => {
  it("exposes only a colour/response layer and no measurement mutation", () => {
    const claim: AgentClaim = {
      schema_version: "agent-claim.v1",
      claim_id: "claim-cycle-1-architecture",
      cycle_id: "cycle-1",
      agent_id: "agent-architecture",
      agent_version: "test-v1",
      role: "architecture",
      lens: "metaphor",
      kind: "observation",
      state: "proposed",
      proposition: "当前空间边界收紧(叙事隐喻)。",
      stance: "supports",
      evidence_refs: ["evidence://sha256:test/signals/motion/state"],
      counter_evidence_refs: [],
      sources: [],
      assumptions: [],
      alternative_explanations: [],
      falsification_test: "下一周期复核。",
      reasoning_summary: "只解释封存代理。",
    };
    const base = initialState();
    const state: StreamState = {
      ...base,
      connection: "online",
      stale: false,
      council: {
        cycles: {
          "cycle-1": {
            cycleId: "cycle-1",
            claims: [claim],
            challenges: [],
            rejections: [],
            result: null,
          },
        },
        order: ["cycle-1"],
        discussionUnavailable: false,
      },
    };

    const { container } = render(
      <AgentResponseOverlay state={state} reducedMotion={false} />,
    );
    const overlay = container.querySelector(".agent-response-overlay");
    expect(overlay?.getAttribute("data-agent-effect")).toBe(
      "colour-and-response-only",
    );
    expect(overlay?.getAttribute("data-measurement-mutation")).toBe("none");
    expect(overlay?.classList.contains("agent-response-architecture")).toBe(true);
    expect(overlay?.querySelectorAll(".agent-response-digit")).toHaveLength(6);
    expect(overlay?.querySelectorAll("i")).toHaveLength(0);
  });
});
