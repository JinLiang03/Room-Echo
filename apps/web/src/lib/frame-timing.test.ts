import { describe, expect, it } from "vitest";
import {
  DROPPED_FRAME_THRESHOLD_MS,
  MAX_SIMULATION_DT_MS,
  measureFrameTiming,
} from "./frame-timing";

describe("measureFrameTiming", () => {
  it("clamps simulation time but reports a real long-frame drop", () => {
    const timing = measureFrameTiming(150, 60);
    expect(timing.simulationDtMs).toBe(MAX_SIMULATION_DT_MS);
    expect(timing.dropped).toBe(true);
    expect(timing.fpsEma).toBeLessThan(60);
  });

  it("does not report ordinary animation frames as dropped", () => {
    const timing = measureFrameTiming(16.7, 60);
    expect(timing.simulationDtMs).toBeCloseTo(16.7);
    expect(timing.dropped).toBe(false);
    expect(DROPPED_FRAME_THRESHOLD_MS).toBeGreaterThan(16.7);
  });
});
