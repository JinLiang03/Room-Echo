import { describe, expect, it } from "vitest";
import { signalTriplets } from "../generated/fixtures";
import {
  deriveLifeState,
  lifeCycleThemes,
  lifeStateDefinition,
  lifeStateThemes,
} from "./life-state";
import type { CouncilResult, SignalTriplet } from "./types";

const base = signalTriplets[1] as SignalTriplet;

function triplet(options: {
  motion?: number;
  low?: number;
  medium?: number;
  high?: number;
  near?: number;
  mid?: number;
  far?: number;
} = {}): SignalTriplet {
  return {
    ...base,
    status: "ok",
    motion: {
      value: options.motion ?? 0.3,
      state: "moving",
      confidence: 0.8,
    },
    occupancy_density: {
      probabilities: {
        low: options.low ?? 0.4,
        medium: options.medium ?? 0.5,
        high: options.high ?? 0.1,
        unknown: 0,
      },
      state: "medium",
      confidence: 0.8,
    },
    depth_zone: {
      probabilities: {
        near: options.near ?? 0.7,
        mid: options.mid ?? 0.25,
        far: options.far ?? 0.05,
        unknown: 0,
      },
      state: "near",
      confidence: 0.8,
    },
    sensor_confidence_cap: 0.8,
  };
}

function result(status: CouncilResult["status"]): CouncilResult {
  return {
    schema_version: "council-result.v1",
    cycle_id: "cycle-life",
    evidence_hash: "sha256:life",
    status,
    headline: "h",
    summary: "s",
    sensor_confidence_cap: 0.8,
    model_support: 0.7,
    display_confidence: 0.7,
    interpretation_agreement: {
      participants: 7,
      supporting: status === "ambiguous" ? 4 : 7,
      contradicting: status === "ambiguous" ? 2 : 0,
      unresolved_challenges: status === "ambiguous" ? 1 : 0,
      agreement_ratio: status === "ambiguous" ? 4 / 7 : 1,
    },
    provenance: {
      contracts_version: "1",
      features_version: "1",
      calibration_profile_id: "demo",
      policy_version: "1",
      generated_at: "2026-08-08T00:00:00Z",
    },
  };
}

describe("digital life state", () => {
  it("prioritizes unknown and disagreement as doubt", () => {
    expect(deriveLifeState({ triplet: null, result: null, stale: true })).toBe("doubt");
    expect(
      deriveLifeState({ triplet: triplet(), result: result("ambiguous"), stale: false }),
    ).toBe("doubt");
  });

  it("lets an explicit, older matching memory become echo", () => {
    expect(
      deriveLifeState({
        triplet: triplet(),
        result: result("supported"),
        stale: false,
        remembered: true,
      }),
    ).toBe("echo");
  });

  it("maps proxy changes into construct, flow, grow, rest, and sound", () => {
    const construct = triplet({ motion: 0.22, near: 0.05, mid: 0.15, far: 0.8 });
    expect(deriveLifeState({ triplet: construct, result: null, stale: false })).toBe("construct");

    const flow = triplet({ motion: 0.86 });
    expect(deriveLifeState({ triplet: flow, result: null, stale: false })).toBe("flow");

    const growthHistory = [
      triplet({ motion: 0.26, low: 0.85, medium: 0.1, high: 0.05 }),
      triplet({ motion: 0.25, low: 0.7, medium: 0.2, high: 0.1 }),
      triplet({ motion: 0.27, low: 0.55, medium: 0.3, high: 0.15 }),
      triplet({ motion: 0.28, low: 0.25, medium: 0.4, high: 0.35 }),
    ];
    expect(
      deriveLifeState({
        triplet: growthHistory.at(-1) ?? null,
        history: growthHistory,
        result: null,
        stale: false,
      }),
    ).toBe("grow");

    const rest = triplet({ motion: 0.08, low: 0.8, medium: 0.18, high: 0.02 });
    expect(deriveLifeState({ triplet: rest, history: [rest], result: null, stale: false })).toBe("rest");

    const sound = triplet({ motion: 0.32, low: 0.4, medium: 0.5, high: 0.1 });
    expect(deriveLifeState({ triplet: sound, history: [sound], result: null, stale: false })).toBe("sound");
  });

  it("describes the one-time plan and volume introduction", () => {
    expect(lifeCycleThemes("flow")).toEqual([
      "floorplan",
      "volume",
      "abstract_presence",
    ]);
    expect(lifeCycleThemes("construct")).toEqual(["floorplan", "volume"]);
  });

  it("maps states to truthful primary bodies and slow visual variants", () => {
    expect(lifeStateDefinition("flow").theme).toBe("abstract_presence");
    expect(lifeStateDefinition("rest").theme).toBe("sofa");
    expect(lifeStateDefinition("sound").theme).toBe("floor_lamp");
    expect(lifeStateThemes("flow")).toEqual(["abstract_presence", "passage"]);
    expect(lifeStateThemes("rest")).toEqual(["sofa", "lounge"]);
    expect(lifeStateThemes("sound")).toEqual(["floor_lamp", "atrium"]);
    expect(lifeStateThemes("doubt")).toEqual(["floorplan"]);
  });
});
