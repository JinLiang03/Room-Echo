import type { CouncilResult, SignalTriplet } from "./types";

/**
 * Deterministic multimodal render mapping (Phase 09).
 *
 * Only approved SignalTriplet/CouncilResult fields are consumed; agent free
 * text never enters the geometry. The same (seed, input, mapping_version)
 * produces the same initial parameters and particle field; animation only
 * advances time.
 */

export const MAPPING_VERSION = "multimodal-v1";
export const VISUAL_SEED = 0x5eed;

export const PARTICLE_SPEED_MIN = 0.08;
export const PARTICLE_SPEED_MAX = 1.8;
export const PULSE_HZ_MIN = 0.12;
export const PULSE_HZ_MAX = 2.4;
export const SATURATION_MIN = 0.2;
export const SATURATION_MAX = 1.0;
export const DEFAULT_DATA_RATE_HZ = 4;

export interface RenderInput {
  triplet: SignalTriplet | null;
  result: CouncilResult | null;
  stale: boolean;
  dataRateHz?: number;
}

export interface RenderParams {
  mapping_version: string;
  particle_speed: number;
  pulse_hz: number;
  field_density: number;
  z_layer_separation: number;
  saturation: number;
  edge_diffusion: number;
  disagreement_phase: number;
  measurement_quality: number;
  active: boolean;
  reason: string;
  data_rate_hz: number;
}

export function clamp01(value: number): number {
  if (!Number.isFinite(value)) {
    return 0;
  }
  return Math.min(1, Math.max(0, value));
}

export function lerp(a: number, b: number, t: number): number {
  return a + (b - a) * clamp01(t);
}

export function measurementQuality(triplet: SignalTriplet | null): number {
  if (!triplet) {
    return 0;
  }
  return safeMin(
    triplet.motion.confidence,
    triplet.occupancy_density.confidence,
    triplet.depth_zone.confidence,
  );
}

function safeMin(...values: number[]): number {
  let result = Infinity;
  for (const value of values) {
    if (Number.isFinite(value)) {
      result = Math.min(result, value);
    }
  }
  return Number.isFinite(result) ? result : 0;
}

export function occupancyWeighted(triplet: SignalTriplet): number {
  const p = triplet.occupancy_density.probabilities;
  return clamp01(p.low * 0.15 + p.medium * 0.5 + p.high * 0.95);
}

export function depthWeighted(triplet: SignalTriplet): number {
  const p = triplet.depth_zone.probabilities;
  return clamp01(p.near * 0.2 + p.mid * 0.5 + p.far * 0.85);
}

export function disagreementPhase(result: CouncilResult | null): number {
  if (!result) {
    return 0;
  }
  const agreement = result.interpretation_agreement;
  const participants = Math.max(1, agreement.participants);
  const contested =
    agreement.contradicting + agreement.unresolved_challenges;
  return clamp01(contested / participants);
}

export function mapRenderParams(input: RenderInput): RenderParams {
  const { triplet, result, stale } = input;
  const dataRateHz =
    input.dataRateHz !== undefined && Number.isFinite(input.dataRateHz)
      ? Math.min(60, Math.max(0.1, input.dataRateHz))
      : DEFAULT_DATA_RATE_HZ;

  if (stale || triplet === null) {
    return {
      mapping_version: MAPPING_VERSION,
      particle_speed: PARTICLE_SPEED_MIN,
      pulse_hz: PULSE_HZ_MIN,
      field_density: 0,
      z_layer_separation: 0,
      saturation: SATURATION_MIN,
      edge_diffusion: 1 - SATURATION_MIN,
      disagreement_phase: 0,
      measurement_quality: 0,
      active: false,
      reason: stale ? "stale" : "no_data",
      data_rate_hz: dataRateHz,
    };
  }

  if (
    triplet.status === "insufficient_signal" ||
    triplet.status === "uncalibrated"
  ) {
    return {
      mapping_version: MAPPING_VERSION,
      particle_speed: PARTICLE_SPEED_MIN,
      pulse_hz: PULSE_HZ_MIN,
      field_density: 0,
      z_layer_separation: 0,
      saturation: SATURATION_MIN,
      edge_diffusion: 1 - SATURATION_MIN,
      disagreement_phase: 0,
      measurement_quality: 0,
      active: false,
      reason: triplet.status,
      data_rate_hz: dataRateHz,
    };
  }

  const motion = clamp01(triplet.motion.value);
  const quality = measurementQuality(triplet);
  const density = occupancyWeighted(triplet);
  const depth = depthWeighted(triplet);

  return {
    mapping_version: MAPPING_VERSION,
    particle_speed: lerp(PARTICLE_SPEED_MIN, PARTICLE_SPEED_MAX, motion),
    pulse_hz: lerp(PULSE_HZ_MIN, PULSE_HZ_MAX, motion),
    field_density: density,
    z_layer_separation: depth,
    saturation: lerp(SATURATION_MIN, SATURATION_MAX, quality),
    edge_diffusion: clamp01(1 - quality),
    disagreement_phase: disagreementPhase(result),
    measurement_quality: quality,
    active: true,
    reason: triplet.status === "degraded" ? "degraded" : "ok",
    data_rate_hz: dataRateHz,
  };
}

/** Deterministic PRNG (mulberry32) — never Math.random in the render path. */
export function mulberry32(seed: number): () => number {
  let state = seed >>> 0;
  return () => {
    state = (state + 0x6d2b79f5) >>> 0;
    let t = state;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

export interface Particle {
  index: number;
  angle: number;
  radius: number;
  size: number;
  phase: number;
  speedFactor: number;
  hue: number;
}

export const PARTICLE_PALETTE = [215, 262, 172]; // blue, violet, teal hues

export function seedParticles(seed: number, count: number): Particle[] {
  const rand = mulberry32(seed);
  const particles: Particle[] = [];
  for (let index = 0; index < count; index += 1) {
    particles.push({
      index,
      angle: rand() * Math.PI * 2,
      radius: 0.08 + rand() * 0.9,
      size: 0.8 + rand() * 2.4,
      phase: rand() * Math.PI * 2,
      speedFactor: 0.4 + rand() * 1.6,
      hue: PARTICLE_PALETTE[index % PARTICLE_PALETTE.length],
    });
  }
  return particles;
}

/** FNV-1a hash of the deterministic render snapshot (tests/debug only). */
export function renderSnapshotHash(params: RenderParams, particles: Particle[]): string {
  let hash = 0x811c9dc5;
  const feed = (value: string) => {
    for (let index = 0; index < value.length; index += 1) {
      hash ^= value.charCodeAt(index);
      hash = Math.imul(hash, 0x01000193) >>> 0;
    }
  };
  feed(JSON.stringify(params));
  feed(particles.map((p) => `${p.index}:${p.angle.toFixed(6)}:${p.radius}`).join("|"));
  return hash.toString(16).padStart(8, "0");
}
