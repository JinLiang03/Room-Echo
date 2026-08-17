import { describe, expect, it } from "vitest";
import {
  MAPPING_VERSION,
  PARTICLE_SPEED_MAX,
  PARTICLE_SPEED_MIN,
  PULSE_HZ_MAX,
  PULSE_HZ_MIN,
  SATURATION_MAX,
  SATURATION_MIN,
  VISUAL_SEED,
  disagreementPhase,
  mapRenderParams,
  mulberry32,
  renderSnapshotHash,
  seedParticles,
} from "./multimodal";
import type { SignalTriplet } from "./types";
import { signalTriplets } from "../generated/fixtures";
import { testActionDecision } from "../test-fixtures";

const moving = signalTriplets[1] as SignalTriplet;
const idle = signalTriplets[0] as SignalTriplet;

function makeResult(status: "supported" | "ambiguous" | "unavailable", contested = 0) {
  return {
    schema_version: "council-result.v1" as const,
    cycle_id: "cycle-1",
    evidence_hash: "sha256:abc",
    status,
    headline: "h",
    summary: "s",
    sensor_confidence_cap: 0.8,
    model_support: 0.8,
    display_confidence: 0.8,
    interpretation_agreement: {
      participants: 4,
      supporting: 4 - contested,
      contradicting: contested,
      unresolved_challenges: 0,
      agreement_ratio: (4 - contested) / 4,
    },
    action_decision: testActionDecision({
      cycleId: "cycle-1",
      evidenceHash: "sha256:abc",
      sensorCap: 0.8,
    }),
    provenance: {
      contracts_version: "1.0.0",
      features_version: "features-v2",
      calibration_profile_id: "demo_room_v1",
      policy_version: "policy-v1",
      generated_at: "2026-08-06T12:00:00Z",
    },
  };
}

describe("multimodal mapping", () => {
  it("implements the exact baseline for a moving triplet", () => {
    const params = mapRenderParams({
      triplet: moving,
      result: makeResult("supported"),
      stale: false,
    });
    expect(params.mapping_version).toBe(MAPPING_VERSION);
    expect(params.active).toBe(true);
    const expectedSpeed = 0.08 + (1.8 - 0.08) * moving.motion.value;
    expect(params.particle_speed).toBeCloseTo(expectedSpeed, 6);
    const expectedPulse = 0.12 + (2.4 - 0.12) * moving.motion.value;
    expect(params.pulse_hz).toBeCloseTo(expectedPulse, 6);
    expect(params.saturation).toBeGreaterThanOrEqual(SATURATION_MIN);
    expect(params.saturation).toBeLessThanOrEqual(SATURATION_MAX);
    expect(params.edge_diffusion).toBeCloseTo(1 - params.measurement_quality, 6);
  });

  it("is deterministic: same input -> identical params and snapshot", () => {
    const input = { triplet: moving, result: makeResult("ambiguous", 1), stale: false };
    const first = mapRenderParams(input);
    const second = mapRenderParams(input);
    expect(first).toEqual(second);
    const particles = seedParticles(VISUAL_SEED, 64);
    expect(renderSnapshotHash(first, particles)).toBe(
      renderSnapshotHash(second, seedParticles(VISUAL_SEED, 64)),
    );
  });

  it("clears state and desaturates on stale and unknown", () => {
    const stale = mapRenderParams({
      triplet: moving,
      result: makeResult("supported"),
      stale: true,
    });
    expect(stale.active).toBe(false);
    expect(stale.saturation).toBe(SATURATION_MIN);
    expect(stale.field_density).toBe(0);
    expect(stale.particle_speed).toBe(PARTICLE_SPEED_MIN);
    expect(stale.reason).toBe("stale");

    const unknown: SignalTriplet = {
      ...moving,
      status: "insufficient_signal",
      motion: { value: 0, state: "unknown", confidence: 0 },
      occupancy_density: {
        probabilities: { low: 0, medium: 0, high: 0, unknown: 1 },
        state: "unknown",
        confidence: 0,
      },
      depth_zone: {
        probabilities: { near: 0, mid: 0, far: 0, unknown: 1 },
        state: "unknown",
        confidence: 0,
      },
      sensor_confidence_cap: 0,
    };
    const cleared = mapRenderParams({
      triplet: unknown,
      result: null,
      stale: false,
    });
    expect(cleared.active).toBe(false);
    expect(cleared.saturation).toBe(SATURATION_MIN);
    expect(cleared.z_layer_separation).toBe(0);
  });

  it("never produces NaN/Infinity even from poisoned inputs", () => {
    const poisoned: SignalTriplet = {
      ...moving,
      motion: { value: Number.NaN, state: "unknown", confidence: Number.POSITIVE_INFINITY },
      occupancy_density: {
        probabilities: {
          low: Number.NEGATIVE_INFINITY,
          medium: Number.NaN,
          high: 2,
          unknown: -1,
        },
        state: "unknown",
        confidence: Number.NaN,
      },
      depth_zone: {
        probabilities: { near: Number.NaN, mid: 0, far: 0, unknown: 1 },
        state: "unknown",
        confidence: 0,
      },
      sensor_confidence_cap: Number.POSITIVE_INFINITY,
    };
    const params = mapRenderParams({
      triplet: poisoned,
      result: null,
      stale: false,
    });
    for (const value of Object.values(params)) {
      if (typeof value === "number") {
        expect(Number.isFinite(value)).toBe(true);
      }
    }
  });

  it("keeps all mapped parameters within documented ranges", () => {
    for (const triplet of [idle, moving]) {
      const params = mapRenderParams({
        triplet,
        result: makeResult("supported"),
        stale: false,
      });
      expect(params.particle_speed).toBeGreaterThanOrEqual(PARTICLE_SPEED_MIN);
      expect(params.particle_speed).toBeLessThanOrEqual(PARTICLE_SPEED_MAX);
      expect(params.pulse_hz).toBeGreaterThanOrEqual(PULSE_HZ_MIN);
      expect(params.pulse_hz).toBeLessThanOrEqual(PULSE_HZ_MAX);
      expect(params.field_density).toBeGreaterThanOrEqual(0);
      expect(params.field_density).toBeLessThanOrEqual(1);
      expect(params.z_layer_separation).toBeGreaterThanOrEqual(0);
      expect(params.z_layer_separation).toBeLessThanOrEqual(1);
      expect(params.disagreement_phase).toBeGreaterThanOrEqual(0);
      expect(params.disagreement_phase).toBeLessThanOrEqual(1);
    }
  });

  it("disagreement only affects phase, never signal values", () => {
    const calm = mapRenderParams({
      triplet: moving,
      result: makeResult("supported", 0),
      stale: false,
    });
    const contested = mapRenderParams({
      triplet: moving,
      result: makeResult("supported", 2),
      stale: false,
    });
    expect(contested.disagreement_phase).toBeGreaterThan(calm.disagreement_phase);
    expect(contested.particle_speed).toBe(calm.particle_speed);
    expect(contested.field_density).toBe(calm.field_density);
    expect(contested.saturation).toBe(calm.saturation);
    expect(contested.z_layer_separation).toBe(calm.z_layer_separation);
  });

  it("seeded particles and PRNG are reproducible", () => {
    const a = seedParticles(12345, 32);
    const b = seedParticles(12345, 32);
    expect(a).toEqual(b);
    const first = mulberry32(7);
    const second = mulberry32(7);
    expect([first(), first(), first()]).toEqual([second(), second(), second()]);
    const other = mulberry32(8);
    expect(other()).not.toBe(second());
    expect(disagreementPhase(null)).toBe(0);
  });
});
