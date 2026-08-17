import {
  clamp01,
  depthWeighted,
  measurementQuality,
  occupancyWeighted,
} from "./multimodal";
import { LIFE_STATE_IDS, type LifeStateId } from "./life-state";
import type { CouncilResult, SignalTriplet } from "./types";

const MEMORY_KEY = "wifi-spatial-council.life-memories.v1";
const MEMORY_LIMIT = 32;
const ECHO_MIN_AGE_MS = 30_000;

export interface LifeMemory {
  id: string;
  createdAt: string;
  lifeState: LifeStateId;
  signature: string;
  motion: number;
  occupancy: number;
  depth: number;
  quality: number;
  cycleId: string | null;
  sourceMode: SignalTriplet["source_mode"] | null;
  sessionId: string | null;
}

export function readLifeMemories(): LifeMemory[] {
  try {
    const raw = window.localStorage.getItem(MEMORY_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw) as unknown;
    if (!Array.isArray(parsed)) return [];
    return parsed.filter(isLifeMemory).slice(0, MEMORY_LIMIT);
  } catch {
    return [];
  }
}

export function saveLifeMemory(input: {
  lifeState: LifeStateId;
  triplet: SignalTriplet | null;
  result: CouncilResult | null;
  now?: Date;
}): LifeMemory {
  const createdAt = (input.now ?? new Date()).toISOString();
  const motion = input.triplet ? clamp01(input.triplet.motion.value) : 0;
  const occupancy = input.triplet ? occupancyWeighted(input.triplet) : 0;
  const depth = input.triplet ? depthWeighted(input.triplet) : 0;
  const quality = input.triplet ? measurementQuality(input.triplet) : 0;
  const signature = hashText(
    [createdAt, input.lifeState, motion, occupancy, depth, input.result?.cycle_id ?? "none"].join("|"),
  );
  const memory: LifeMemory = {
    id: `echo-${signature}`,
    createdAt,
    lifeState: input.lifeState,
    signature,
    motion,
    occupancy,
    depth,
    quality,
    cycleId: input.result?.cycle_id ?? null,
    sourceMode: input.triplet?.source_mode ?? null,
    sessionId: input.triplet?.session_id ?? null,
  };
  writeLifeMemories([memory, ...readLifeMemories()].slice(0, MEMORY_LIMIT));
  return memory;
}

export function deleteLifeMemory(id: string): LifeMemory[] {
  const next = readLifeMemories().filter((memory) => memory.id !== id);
  writeLifeMemories(next);
  return next;
}

export function findEchoMemory(
  triplet: SignalTriplet | null,
  memories: readonly LifeMemory[],
  now = Date.now(),
): LifeMemory | null {
  if (!triplet || measurementQuality(triplet) < 0.35) return null;
  const current = {
    motion: clamp01(triplet.motion.value),
    occupancy: occupancyWeighted(triplet),
    depth: depthWeighted(triplet),
  };
  let best: { memory: LifeMemory; distance: number } | null = null;
  for (const memory of memories) {
    if (
      memory.quality < 0.35 ||
      memory.sourceMode !== triplet.source_mode ||
      memory.sessionId !== triplet.session_id
    ) {
      continue;
    }
    const age = now - new Date(memory.createdAt).getTime();
    if (!Number.isFinite(age) || age < ECHO_MIN_AGE_MS) continue;
    const distance = Math.hypot(
      current.motion - memory.motion,
      current.occupancy - memory.occupancy,
      current.depth - memory.depth,
    );
    if (distance <= 0.16 && (!best || distance < best.distance)) {
      best = { memory, distance };
    }
  }
  return best?.memory ?? null;
}

function writeLifeMemories(memories: readonly LifeMemory[]): void {
  try {
    window.localStorage.setItem(MEMORY_KEY, JSON.stringify(memories));
  } catch {
    // Local visual memory is best-effort; the live signal path must continue.
  }
}

function hashText(text: string): string {
  let hash = 0x811c9dc5;
  for (let index = 0; index < text.length; index += 1) {
    hash ^= text.charCodeAt(index);
    hash = Math.imul(hash, 0x01000193) >>> 0;
  }
  return hash.toString(16).padStart(8, "0");
}

function isLifeMemory(value: unknown): value is LifeMemory {
  if (!value || typeof value !== "object") return false;
  const item = value as Partial<LifeMemory>;
  return (
    typeof item.id === "string" &&
    typeof item.createdAt === "string" &&
    typeof item.lifeState === "string" &&
    LIFE_STATE_IDS.includes(item.lifeState as LifeStateId) &&
    typeof item.signature === "string" &&
    typeof item.motion === "number" &&
    typeof item.occupancy === "number" &&
    typeof item.depth === "number" &&
    typeof item.quality === "number" &&
    (item.sourceMode === null ||
      item.sourceMode === "mock" ||
      item.sourceMode === "replay" ||
      item.sourceMode === "live") &&
    (item.sessionId === null || typeof item.sessionId === "string")
  );
}
