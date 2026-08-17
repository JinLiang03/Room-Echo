import type { CouncilResult } from "./types";
import type { SpatialThemeId } from "./spatial-themes";

type AgentEffect = NonNullable<CouncilResult["life_interaction"]>["effect"];

/**
 * The Fusion result selects a generative visual metaphor for Home. This is a
 * presentation decision only: it never changes the sealed measurements,
 * confidence, or the signal-to-motion mapping.
 */
const EFFECT_THEME: Record<AgentEffect, SpatialThemeId> = {
  contract: "floorplan",
  expand: "lounge",
  block: "floorplan",
  rest: "sofa",
  startle: "floor_lamp",
  recover: "sofa",
  gather: "atrium",
  scatter: "passage",
  stagnate: "floorplan",
  surge: "floor_lamp",
  settle: "sofa",
  activate: "floor_lamp",
  alert: "floor_lamp",
  float: "abstract_presence",
  hold: "abstract_presence",
  verify: "abstract_presence",
  echo: "studio",
};

export function themeForAgentResult(
  result: CouncilResult | null,
  fallback: SpatialThemeId,
): SpatialThemeId {
  if (!result || result.status === "unavailable") return fallback;
  const effect = result.life_interaction?.effect;
  return effect ? EFFECT_THEME[effect] : fallback;
}
