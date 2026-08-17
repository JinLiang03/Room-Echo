import {
  clamp01,
  depthWeighted,
  disagreementPhase,
  occupancyWeighted,
} from "./multimodal";
import type { SpatialThemeId } from "./spatial-themes";
import type { CouncilResult, SignalTriplet } from "./types";

export const LIFE_STATE_IDS = [
  "construct",
  "flow",
  "rest",
  "grow",
  "sound",
  "doubt",
  "echo",
] as const;

export type LifeStateId = (typeof LIFE_STATE_IDS)[number];

export interface LifeStateDefinition {
  id: LifeStateId;
  label: string;
  role: "architecture" | "feng_shui" | "psyche" | "biota" | "soundscape" | "skeptic" | "fusion";
  theme: SpatialThemeId;
}

const LIFE_STATE_THEMES = {
  construct: ["volume"],
  flow: ["abstract_presence", "passage"],
  rest: ["sofa", "lounge"],
  grow: ["garden"],
  sound: ["floor_lamp", "atrium"],
  // A doubtful reading should stay visibly provisional and non-rectangular;
  // the outer digit perimeter remains the spatial frame around it.
  doubt: ["abstract_presence"],
  echo: ["studio"],
} as const satisfies Record<LifeStateId, readonly SpatialThemeId[]>;

export const LIFE_STATES: Record<LifeStateId, LifeStateDefinition> = {
  construct: { id: "construct", label: "构造", role: "architecture", theme: "volume" },
  flow: { id: "flow", label: "流动", role: "feng_shui", theme: "abstract_presence" },
  rest: { id: "rest", label: "栖息", role: "psyche", theme: "sofa" },
  grow: { id: "grow", label: "生长", role: "biota", theme: "garden" },
  sound: { id: "sound", label: "声息", role: "soundscape", theme: "floor_lamp" },
  doubt: { id: "doubt", label: "怀疑", role: "skeptic", theme: "abstract_presence" },
  echo: { id: "echo", label: "回声", role: "fusion", theme: "studio" },
};

export interface LifeStateInput {
  triplet: SignalTriplet | null;
  history?: readonly SignalTriplet[];
  result: CouncilResult | null;
  stale: boolean;
  remembered?: boolean;
}

/**
 * Selects one expressive state from approved proxy signals and Council
 * disagreement. It never infers identity, actions, or user emotion.
 */
export function deriveLifeState(input: LifeStateInput): LifeStateId {
  const { triplet, result, stale } = input;
  if (
    stale ||
    !triplet ||
    triplet.status === "insufficient_signal" ||
    triplet.status === "uncalibrated" ||
    result?.status === "unavailable"
  ) {
    return "doubt";
  }

  if (result?.status === "ambiguous" || disagreementPhase(result) >= 0.2) {
    return "doubt";
  }

  if (input.remembered) {
    return "echo";
  }

  const motion = clamp01(triplet.motion.value);
  const density = occupancyWeighted(triplet);
  const depth = depthWeighted(triplet);
  const recent = (input.history ?? [])
    .filter(isUsableTriplet)
    .slice(-12);
  const previous = recent.at(-2) ?? null;
  const oldest = recent.at(0) ?? null;
  const motionDelta = previous
    ? Math.abs(motion - clamp01(previous.motion.value))
    : 0;
  const densityTrend = oldest
    ? density - occupancyWeighted(oldest)
    : 0;
  const depthTrend = oldest ? depth - depthWeighted(oldest) : 0;
  const meanMotion = recent.length
    ? recent.reduce((sum, item) => sum + clamp01(item.motion.value), 0) / recent.length
    : motion;

  if (Math.abs(depthTrend) >= 0.16 || (depth >= 0.68 && motion < 0.52)) {
    return "construct";
  }
  if (motion >= 0.5 || motionDelta >= 0.2) {
    return "flow";
  }
  if (
    recent.length >= 4 &&
    meanMotion < 0.44 &&
    (densityTrend >= 0.08 || depthTrend >= 0.1)
  ) {
    return "grow";
  }
  if (motion <= 0.18 && meanMotion <= 0.2 && density <= 0.62) {
    return "rest";
  }
  return "sound";
}

export function lifeStateDefinition(id: LifeStateId): LifeStateDefinition {
  return LIFE_STATES[id];
}

/**
 * Deterministic presentation variants for the same signal-selected state.
 * They never change measurements, confidence, or the selected life state.
 */
export function lifeStateThemes(id: LifeStateId): readonly SpatialThemeId[] {
  return LIFE_STATE_THEMES[id];
}

export function lifeCycleThemes(id: LifeStateId): SpatialThemeId[] {
  const target = LIFE_STATES[id].theme;
  return [...new Set<SpatialThemeId>(["floorplan", "volume", target])];
}

function isUsableTriplet(item: SignalTriplet): boolean {
  return item.status !== "insufficient_signal" && item.status !== "uncalibrated";
}
