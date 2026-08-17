import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
  SoundscapeEngine,
  type SoundGraph,
} from "./audio";
import { mapRenderParams } from "./multimodal";
import type { SignalTriplet } from "./types";
import { signalTriplets } from "../generated/fixtures";

class FakeGraph implements SoundGraph {
  nodeCount = 4;
  muted = true;
  calls: string[] = [];
  fadeCalls: number[] = [];
  disposed = false;

  setTempo(hz: number): void {
    this.calls.push(`tempo:${hz.toFixed(3)}`);
  }

  setHarmonicDensity(density: number): void {
    this.calls.push(`density:${density.toFixed(3)}`);
  }

  setFilterCutoff(hz: number): void {
    this.calls.push(`cutoff:${hz.toFixed(1)}`);
  }

  setStereoWidth(width: number): void {
    this.calls.push(`width:${width.toFixed(3)}`);
  }

  setClarity(clarity: number): void {
    this.calls.push(`clarity:${clarity.toFixed(3)}`);
  }

  setMuted(muted: boolean): void {
    this.muted = muted;
    this.calls.push(`muted:${muted}`);
  }

  fadeTo(gain: number, durationMs: number): void {
    this.fadeCalls.push(gain);
    void durationMs;
  }

  dispose(): void {
    this.disposed = true;
  }
}

const moving = signalTriplets[1] as SignalTriplet;

function params(triplet: SignalTriplet | null, stale = false) {
  return mapRenderParams({ triplet, result: null, stale });
}

describe("SoundscapeEngine", () => {
  let graph: FakeGraph;
  let engine: SoundscapeEngine;

  beforeEach(() => {
    graph = new FakeGraph();
    engine = new SoundscapeEngine({
      createGraph: () => graph,
      tickIntervalMs: 100,
    });
    vi.useFakeTimers();
  });

  afterEach(() => {
    engine.dispose();
    vi.useRealTimers();
  });

  it("does not create audio until enabled by a user gesture", () => {
    expect(engine.stats.enabled).toBe(false);
    expect(engine.stats.nodeCount).toBe(0);
    engine.update(params(moving));
    expect(engine.stats.nodeCount).toBe(0);
  });

  it("defaults to muted even after enable", () => {
    engine.enable();
    expect(engine.stats.enabled).toBe(true);
    expect(engine.stats.muted).toBe(true);
    expect(graph.fadeCalls.at(-1)).toBe(0);
  });

  it("unmutes and maps params deterministically", () => {
    engine.enable();
    engine.setMuted(false);
    engine.update(params(moving));
    expect(graph.muted).toBe(false);
    expect(graph.fadeCalls.at(-1)).toBe(1);
    expect(graph.calls.some((call) => call.startsWith("tempo:"))).toBe(true);
    expect(graph.calls.some((call) => call.startsWith("cutoff:"))).toBe(true);
    const first = [...graph.calls];
    const graph2 = new FakeGraph();
    const engine2 = new SoundscapeEngine({ createGraph: () => graph2 });
    engine2.enable();
    engine2.setMuted(false);
    engine2.update(params(moving));
    engine2.dispose();
    expect(graph2.calls).toEqual(first);
  });

  it("fades out on pause/stop/blur and back in when not muted", () => {
    engine.enable();
    engine.setMuted(false);
    engine.fadeOut();
    expect(graph.fadeCalls.at(-1)).toBe(0);
    engine.fadeIn();
    expect(graph.fadeCalls.at(-1)).toBe(1);
    engine.setMuted(true);
    engine.fadeIn();
    expect(graph.fadeCalls.at(-1)).toBe(0);
  });

  it("survives high-frequency updates without growing node count", () => {
    engine.enable();
    engine.setMuted(false);
    for (let index = 0; index < 2000; index += 1) {
      const triplet: SignalTriplet = {
        ...moving,
        motion: { ...moving.motion, value: (index % 100) / 100 },
      };
      engine.update(params(triplet));
    }
    expect(graph.nodeCount).toBe(4);
    expect(engine.stats.nodeCount).toBe(4);
  });

  it("cleans up timers and graph on dispose", () => {
    engine.enable();
    engine.dispose();
    expect(graph.disposed).toBe(true);
    expect(engine.stats.enabled).toBe(false);
    expect(engine.stats.nodeCount).toBe(0);
  });

  it("fades to silence when the sculpture becomes inactive", () => {
    engine.enable();
    engine.setMuted(false);
    engine.update(params(moving));
    engine.update(params(moving, true)); // stale
    expect(engine.stats.active).toBe(false);
  });
});
