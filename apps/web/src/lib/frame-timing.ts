export const MAX_SIMULATION_DT_MS = 50;
export const DROPPED_FRAME_THRESHOLD_MS = 100;

export interface FrameTiming {
  simulationDtMs: number;
  fpsEma: number;
  dropped: boolean;
}

/** Keep simulation stable without hiding real browser stalls from telemetry. */
export function measureFrameTiming(
  elapsedMs: number,
  previousFpsEma: number,
): FrameTiming {
  const actualElapsedMs =
    Number.isFinite(elapsedMs) && elapsedMs > 0 ? elapsedMs : 0;
  return {
    simulationDtMs: Math.min(MAX_SIMULATION_DT_MS, actualElapsedMs),
    fpsEma:
      actualElapsedMs > 0
        ? previousFpsEma * 0.9 + (1000 / actualElapsedMs) * 0.1
        : previousFpsEma,
    dropped: actualElapsedMs > DROPPED_FRAME_THRESHOLD_MS,
  };
}
