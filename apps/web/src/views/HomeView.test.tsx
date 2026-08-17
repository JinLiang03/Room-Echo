import { beforeEach, describe, expect, it } from "vitest";
import { initialState } from "../lib/state";
import { renderWithStream } from "../test-utils";
import type { CouncilResult, SignalTriplet } from "../lib/types";
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
  });
});
