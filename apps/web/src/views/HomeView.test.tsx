import { beforeEach, describe, expect, it } from "vitest";
import { initialState } from "../lib/state";
import { simulatedCareScenarios } from "../generated/fixtures";
import { renderWithStream, renderWithStreamAndCare } from "../test-utils";
import { testActionDecision } from "../test-fixtures";
import type { CouncilResult, SignalTriplet } from "../lib/types";
import { CARE_MOMENT_ORDER } from "../lib/care";
import { HomeView } from "./HomeView";

const triplet: SignalTriplet = {
  schema_version: "1.0.0",
  session_id: "session-home",
  window_id: "window-home",
  source_mode: "replay",
  started_at: "2026-08-10T00:00:00Z",
  ended_at: "2026-08-10T00:00:00.250Z",
  motion: { value: 0.88, state: "fast_change", confidence: 0.8 },
  occupancy_density: {
    probabilities: { low: 0.1, medium: 0.2, high: 0.66, unknown: 0.04 },
    state: "high",
    confidence: 0.66,
  },
  depth_zone: {
    probabilities: { near: 0.24, mid: 0.62, far: 0.1, unknown: 0.04 },
    state: "mid",
    confidence: 0.62,
  },
  sensor_confidence_cap: 0.66,
  evidence_refs: ["evidence://sha256:home/signals"],
  status: "ok",
};

const ambiguousResult: CouncilResult = {
  schema_version: "council-result.v1",
  cycle_id: "cycle-home",
  evidence_hash: "sha256:home",
  status: "ambiguous",
  headline: "本轮有分歧",
  summary: "Agent 对同一证据仍有分歧。",
  sensor_confidence_cap: 0.66,
  model_support: 0.5,
  display_confidence: 0.5,
  interpretation_agreement: {
    participants: 7,
    supporting: 4,
    contradicting: 2,
    unresolved_challenges: 1,
    agreement_ratio: 4 / 7,
  },
  action_decision: testActionDecision({
    cycleId: "cycle-home",
    evidenceHash: "sha256:home",
    sensorCap: 0.66,
  }),
  provenance: {
    contracts_version: "1.0.0",
    features_version: "features-v2",
    calibration_profile_id: "demo_room_v1",
    policy_version: "policy-v1",
    generated_at: "2026-08-10T00:00:01Z",
  },
};

describe("HomeView", () => {
  beforeEach(() => window.localStorage.clear());

  it("keeps the upper body's base state signal-driven when Council disagrees", () => {
    const state = initialState();
    state.connection = "online";
    state.triplet = triplet;
    state.history = [triplet];
    state.council = {
      cycles: {
        "cycle-home": {
          cycleId: "cycle-home",
          evidenceHash: "sha256:home",
          signalSnapshot: triplet,
          claims: [],
          challenges: [],
          rejections: [],
          result: ambiguousResult,
        },
      },
      order: ["cycle-home"],
      discussionUnavailable: false,
    };

    const { container } = renderWithStream(<HomeView />, state);

    // fast_change maps to flow. If CouncilResult still drove the base body,
    // this deliberately ambiguous result would force the doubt shape instead.
    expect(container.querySelector(".digit-field")?.getAttribute("data-life-state")).toBe(
      "flow",
    );
    expect(container.querySelectorAll('[data-public-agent="room-echo"]')).toHaveLength(1);
    expect(container.querySelector('[data-care-simulation="true"]')).toBeNull();
    expect(getText(container, ".room-agent h1")).toBe("这一刻仍有歧义");
    expect(container.querySelectorAll(".action-suggestion")).toHaveLength(4);
    expect(container.querySelector('[data-action-status="simulated_preview"]')).not.toBeNull();
    expect(container.querySelector(".digit-field")?.getAttribute("data-show-perimeter"))
      .toBe("false");
    expect(container.querySelector(".room-echo-context")).toBeNull();
    expect(container.querySelector(".care-scenario-selector")).toBeNull();
    expect(container.querySelector(".room-agent-status")?.children).toHaveLength(2);
    expect(container.querySelector(".room-agent-confidence")).toBeNull();
    expect(container.querySelector(".agent-voice-river")).toBeNull();
  });

  it("shows one concrete care Agent and four bounded scenario suggestions", () => {
    const state = initialState();
    state.connection = "online";
    state.triplet = triplet;
    state.history = [triplet];

    const { container, getByText, queryByText } = renderWithStreamAndCare(
      <HomeView />,
      simulatedCareScenarios[0],
      state,
      "bathroom_timeout",
    );

    expect(container.querySelectorAll('[data-public-agent="room-echo"]')).toHaveLength(1);
    expect(container.querySelector('[data-care-simulation="true"]')).not.toBeNull();
    expect(getByText("卫生间停留超过模拟关注阈值")).toBeDefined();
    expect(
      getByText(/模拟外部区域标签显示：卫生间停留 31 分钟/),
    ).toBeDefined();
    expect(container.querySelectorAll('[data-action-source="care_workflow"]')).toHaveLength(4);
    expect(getByText("SIM · CARE")).toBeDefined();
    expect(queryByText("SIMULATION PREVIEW")).toBeNull();
    expect(getByText("模拟预览 · 未连接灯具")).toBeDefined();
    expect(getByText("模拟预览 · 未连接音箱")).toBeDefined();
    expect(getByText("模拟预览 · 未发送消息")).toBeDefined();
    expect(getByText("模拟预览 · 未创建任务")).toBeDefined();
    expect(container.querySelector(".room-echo-context")).toBeNull();
    expect(container.querySelector(".care-scenario-selector")).toBeNull();
    expect(container.querySelector(".action-suggestion footer")).toBeNull();
    const moment = simulatedCareScenarios[0].moments.find(
      (item) => item.moment === "bathroom_timeout",
    );
    const proxy = moment?.evidence_core.proxy_triplet;
    expect(proxy).toBeDefined();
    expect(container.querySelector(".digit-field")?.getAttribute("data-life-state"))
      .toBe("sound");
    for (const selector of [
      '[data-public-agent="room-echo"]',
      ".agent-action-window",
      ".digit-field",
    ]) {
      const element = container.querySelector(selector);
      expect(element?.getAttribute("data-evidence-hash")).toBe(moment?.evidence_hash);
      expect(element?.getAttribute("data-session-id")).toBe(proxy?.session_id);
      expect(element?.getAttribute("data-window-id")).toBe(proxy?.window_id);
    }
  });

  it("atomically binds every accelerated care frame to one Agent, action set, and field", () => {
    const state = initialState();
    state.connection = "online";
    state.triplet = triplet;
    state.history = [triplet];
    const expectedLifeState = {
      routine: "sound",
      bathroom_timeout: "sound",
      fall_drill: "flow",
      pet_night: "flow",
    } as const;

    for (const key of CARE_MOMENT_ORDER) {
      const moment = simulatedCareScenarios[0].moments.find(
        (candidate) => candidate.moment === key,
      );
      expect(moment).toBeDefined();
      const proxy = moment?.evidence_core.proxy_triplet;
      const { container, unmount } = renderWithStreamAndCare(
        <HomeView />,
        simulatedCareScenarios[0],
        state,
        key,
      );
      const agent = container.querySelector('[data-public-agent="room-echo"]');
      const actions = container.querySelector(".agent-action-window");
      const field = container.querySelector(".digit-field");

      expect(agent?.getAttribute("data-care-moment")).toBe(key);
      expect(container.querySelectorAll('[data-action-source="care_workflow"]'))
        .toHaveLength(4);
      for (const element of [agent, actions, field]) {
        expect(element?.getAttribute("data-evidence-hash")).toBe(moment?.evidence_hash);
        expect(element?.getAttribute("data-session-id")).toBe(proxy?.session_id);
        expect(element?.getAttribute("data-window-id")).toBe(proxy?.window_id);
      }
      expect(field?.getAttribute("data-life-state")).toBe(expectedLifeState[key]);
      expect(field?.getAttribute("data-life-active")).toBe("true");
      expect(field?.getAttribute("data-fluid-mode")).toBe(key);
      unmount();
    }
  });

  it("fails a degraded unknown care frame closed without leaking the replay stream", () => {
    const state = initialState();
    state.connection = "online";
    state.triplet = triplet;
    state.history = [triplet];
    const scenario = structuredClone(simulatedCareScenarios[0]);
    const moment = scenario.moments.find(
      (candidate) => candidate.moment === "bathroom_timeout",
    );
    if (!moment) throw new Error("bathroom care fixture missing");
    moment.interpretation_status = "unknown";
    moment.evidence_core.proxy_triplet.status = "degraded";

    const { container, getByText, queryByText } = renderWithStreamAndCare(
      <HomeView />,
      scenario,
      state,
      "bathroom_timeout",
    );

    expect(getByText("暂时无法判断")).toBeDefined();
    expect(queryByText("卫生间停留超过模拟关注阈值")).toBeNull();
    expect(container.querySelectorAll('[data-action-source="care_workflow"]'))
      .toHaveLength(4);
    expect(container.querySelectorAll('[data-action-status="withheld"]'))
      .toHaveLength(4);
    expect(container.querySelector(".digit-field")?.getAttribute("data-life-active"))
      .toBe("false");
    for (const selector of [
      '[data-public-agent="room-echo"]',
      ".agent-action-window",
      ".digit-field",
    ]) {
      const element = container.querySelector(selector);
      expect(element?.getAttribute("data-evidence-hash")).toBe("waiting");
      expect(element?.getAttribute("data-session-id")).toBe("waiting");
      expect(element?.getAttribute("data-window-id")).toBe("waiting");
      expect(element?.getAttribute("data-session-id")).not.toBe(triplet.session_id);
    }
  });
});

function getText(container: HTMLElement, selector: string): string | null {
  return container.querySelector(selector)?.textContent ?? null;
}
