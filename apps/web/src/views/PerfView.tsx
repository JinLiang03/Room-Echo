import { useCallback, useEffect, useRef, useState } from "react";
import { SignalSculpture } from "../components/SignalSculpture";
import { SoundscapeEngine } from "../lib/audio";
import { mapRenderParams } from "../lib/multimodal";
import type { SignalTriplet } from "../lib/types";
import { signalTriplets } from "../generated/fixtures";
import { routeParams } from "../lib/router";
import { DigitSectionMark } from "../components/DigitSectionMark";

declare global {
  interface Window {
    __wscPerf?: {
      fps: number;
      drawCalls: number;
      dropped: number;
      eventsInjected: number;
      nodeCount: number;
      done: boolean;
      startedAt: number;
    };
  }
}

/**
 * Headless performance harness at #/perf?seconds=8&rate=24.
 * Drives the sculpture + audio with a scripted high-rate event feed and
 * exposes window.__wscPerf for the perf smoke script.
 */
export function PerfView() {
  const params = routeParams();
  const seconds = Number(params.get("seconds") ?? 8);
  const rate = Number(params.get("rate") ?? 24);
  const [triplet, setTriplet] = useState<SignalTriplet>(
    signalTriplets[1] as SignalTriplet,
  );
  const fpsRef = useRef(0);
  const drawsRef = useRef(0);
  const droppedRef = useRef(0);
  const nodeCountRef = useRef(0);
  const injectedRef = useRef(0);

  const onStats = useCallback(
    (stats: { fps: number; drawCalls: number; dropped: number }) => {
      fpsRef.current = stats.fps;
      drawsRef.current = stats.drawCalls;
      droppedRef.current = stats.dropped;
    },
    [],
  );

  useEffect(() => {
    // Harness simulates the user gesture that normally enables audio.
    const engine = new SoundscapeEngine();
    engine.enable();
    engine.setMuted(false);

    const base = signalTriplets[1] as SignalTriplet;
    const intervalMs = Math.max(25, 1000 / Math.max(1, rate));
    const startedAt = performance.now();
    const timer = window.setInterval(() => {
      injectedRef.current += 1;
      const phase = (injectedRef.current % 12) / 12;
      const next: SignalTriplet = {
        ...base,
        window_id: `perf-${injectedRef.current}`,
        motion: {
          ...base.motion,
          value:
            0.15 + Math.abs(Math.sin(phase * Math.PI * 2)) * 0.8,
        },
        occupancy_density: {
          ...base.occupancy_density,
          state:
            phase > 0.7 ? "high" : phase > 0.4 ? "medium" : "low",
        },
        depth_zone: {
          ...base.depth_zone,
          state: phase > 0.8 ? "far" : phase > 0.5 ? "mid" : "near",
        },
      };
      setTriplet(next);
      engine.update(
        mapRenderParams({
          triplet: next,
          result: null,
          stale: false,
        }),
      );
    }, intervalMs);

    const statsTimer = window.setInterval(() => {
      nodeCountRef.current = engine.stats.nodeCount;
      if (performance.now() - startedAt >= seconds * 1000) {
        window.__wscPerf = {
          fps: fpsRef.current,
          drawCalls: drawsRef.current,
          dropped: droppedRef.current,
          eventsInjected: injectedRef.current,
          nodeCount: nodeCountRef.current,
          done: true,
          startedAt,
        };
        window.clearInterval(statsTimer);
        window.clearInterval(timer);
      }
    }, 250);

    return () => {
      window.clearInterval(timer);
      window.clearInterval(statsTimer);
      engine.dispose();
    };
  }, [rate, seconds]);

  return (
    <section className="perf-view" aria-label="性能调试">
      <h2 className="digit-heading">
        <DigitSectionMark role="soundscape" seed="perf-title" size="medium" />
        <span>Multimodal perf harness</span>
      </h2>
      <SignalSculpture
        triplet={triplet}
        result={null}
        stale={false}
        debug
        onStats={onStats}
      />
      <p className="chart-note">
        事件注入 {rate} Hz · {seconds}s · 统计写 window.__wscPerf
      </p>
    </section>
  );
}
