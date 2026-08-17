import type { RenderParams } from "./multimodal";

/**
 * Soundscape engine (Phase 09).
 *
 * Audio never autoplays: the engine only activates on a user gesture
 * (`enable()`), defaults to muted, and fades out on pause/stop/blur. Mapping
 * is deterministic from RenderParams; no alarm-like or danger sounds are
 * used — disagreement produces a very light phase beat only.
 */

export interface SoundGraph {
  readonly nodeCount: number;
  setTempo(hz: number): void;
  setHarmonicDensity(density: number): void;
  setFilterCutoff(hz: number): void;
  setStereoWidth(width: number): void;
  setClarity(clarity: number): void;
  setMuted(muted: boolean): void;
  fadeTo(gain: number, durationMs: number): void;
  dispose(): void;
}

export type SoundGraphFactory = () => SoundGraph;

export interface SoundscapeEngineOptions {
  createGraph?: SoundGraphFactory;
  tickIntervalMs?: number;
}

export interface SoundscapeStats {
  enabled: boolean;
  muted: boolean;
  nodeCount: number;
  active: boolean;
}

const FADE_MS = 350;

export class SoundscapeEngine {
  private graph: SoundGraph | null = null;
  private muted = true;
  private enabled = false;
  private disposed = false;
  private ticker: number | null = null;
  private target: RenderParams | null = null;
  private current = {
    tempo: 0.3,
    harmonicDensity: 0,
    cutoff: 300,
    width: 0.1,
    clarity: 0.2,
  };
  private readonly tickIntervalMs: number;
  private readonly createGraph: SoundGraphFactory;
  private listeners = new Set<() => void>();

  constructor(options: SoundscapeEngineOptions = {}) {
    this.createGraph = options.createGraph ?? createWebAudioGraph;
    this.tickIntervalMs = options.tickIntervalMs ?? 100;
  }

  get stats(): SoundscapeStats {
    return {
      enabled: this.enabled,
      muted: this.muted,
      nodeCount: this.graph?.nodeCount ?? 0,
      active: this.graph !== null && !this.muted && this.target?.active === true,
    };
  }

  subscribe(listener: () => void): () => void {
    this.listeners.add(listener);
    return () => this.listeners.delete(listener);
  }

  /** Must be called from a user gesture (click/keydown). */
  enable(): void {
    if (this.disposed || this.enabled) {
      return;
    }
    this.graph = this.createGraph();
    this.enabled = true;
    this.graph.setMuted(this.muted);
    this.graph.fadeTo(this.muted ? 0 : 1, FADE_MS);
    this.startTicker();
    this.notify();
  }

  setMuted(muted: boolean): void {
    this.muted = muted;
    this.graph?.setMuted(muted);
    this.graph?.fadeTo(muted ? 0 : 1, FADE_MS);
    this.notify();
  }

  update(params: RenderParams): void {
    this.target = params;
    if (!this.enabled || !this.graph) {
      return;
    }
    // Smooth toward the mapped targets each tick (no jumps).
    const g = this.graph;
    const nextTempo = params.active
      ? 0.3 + params.particle_speed * 1.2
      : 0.3;
    const nextCutoff = params.active
      ? 220 + params.field_density * 2400
      : 220;
    const nextWidth = params.active ? 0.1 + params.z_layer_separation * 0.8 : 0.1;
    const nextClarity = params.active ? params.saturation : SATURATION_FLOOR;
    this.current = {
      tempo: smooth(this.current.tempo, nextTempo),
      harmonicDensity: smooth(this.current.harmonicDensity, params.field_density),
      cutoff: smooth(this.current.cutoff, nextCutoff),
      width: smooth(this.current.width, nextWidth),
      clarity: smooth(this.current.clarity, nextClarity),
    };
    g.setTempo(this.current.tempo);
    g.setHarmonicDensity(this.current.harmonicDensity);
    g.setFilterCutoff(this.current.cutoff);
    g.setStereoWidth(this.current.width);
    g.setClarity(this.current.clarity);
  }

  /** Fade out for pause/stop/blur while keeping the graph alive. */
  fadeOut(durationMs = FADE_MS): void {
    this.graph?.fadeTo(0, durationMs);
  }

  /** Restore volume after focus/visibility returns (if not muted). */
  fadeIn(durationMs = FADE_MS): void {
    if (this.graph && !this.muted) {
      this.graph.fadeTo(1, durationMs);
    }
  }

  dispose(): void {
    this.disposed = true;
    if (this.ticker !== null) {
      window.clearInterval(this.ticker);
      this.ticker = null;
    }
    this.graph?.dispose();
    this.graph = null;
    this.enabled = false;
    this.notify();
  }

  private startTicker(): void {
    if (this.ticker !== null) {
      return;
    }
    this.ticker = window.setInterval(() => {
      if (this.target) {
        this.update(this.target);
      }
    }, this.tickIntervalMs);
  }

  private notify(): void {
    for (const listener of this.listeners) {
      listener();
    }
  }
}

const SATURATION_FLOOR = 0.2;

function smooth(current: number, target: number, alpha = 0.35): number {
  return current + (target - current) * alpha;
}

/** Real Web Audio graph. Created only inside a user gesture. */
export function createWebAudioGraph(): SoundGraph {
  const AudioCtor =
    window.AudioContext ??
    (window as unknown as { webkitAudioContext?: typeof AudioContext })
      .webkitAudioContext;
  if (!AudioCtor) {
    throw new Error("Web Audio not available");
  }
  const context = new AudioCtor();
  const master = context.createGain();
  master.gain.value = 0;
  master.connect(context.destination);

  // Pulse layer: short blips at `tempo`.
  const pulseGain = context.createGain();
  pulseGain.gain.value = 0.05;
  pulseGain.connect(master);

  // Harmonic drone layer through a lowpass filter + feedback delay (depth).
  const drone = context.createOscillator();
  drone.type = "sine";
  drone.frequency.value = 55;
  const detuned: OscillatorNode[] = [];
  const droneFilter = context.createBiquadFilter();
  droneFilter.type = "lowpass";
  droneFilter.frequency.value = 300;
  const droneGain = context.createGain();
  droneGain.gain.value = 0.035;
  const panner = context.createStereoPanner();
  panner.pan.value = 0;
  const delay = context.createDelay(1.5);
  delay.delayTime.value = 0.32;
  const feedback = context.createGain();
  feedback.gain.value = 0.35;
  const clarityFilter = context.createBiquadFilter();
  clarityFilter.type = "highpass";
  clarityFilter.frequency.value = 120;

  drone.connect(droneFilter);
  droneFilter.connect(droneGain);
  droneGain.connect(panner);
  panner.connect(delay);
  delay.connect(feedback);
  feedback.connect(delay);
  panner.connect(clarityFilter);
  clarityFilter.connect(master);
  drone.start();

  let muted = true;
  let scheduled: number | null = null;
  let tempoHz = 0.3;

  const graph: SoundGraph = {
    get nodeCount(): number {
      return 8 + detuned.length;
    },
    setTempo(hz: number): void {
      tempoHz = hz;
      if (muted || scheduled !== null) {
        return;
      }
      schedulePulse();
    },
    setHarmonicDensity(density: number): void {
      const wanted = Math.round(density * 4);
      while (detuned.length < wanted) {
        const osc = context.createOscillator();
        osc.type = "triangle";
        osc.frequency.value = 110 + detuned.length * 6;
        osc.detune.value = detuned.length * 3;
        const gain = context.createGain();
        gain.gain.value = 0.012;
        osc.connect(gain);
        gain.connect(droneFilter);
        osc.start();
        detuned.push(osc);
      }
      while (detuned.length > wanted) {
        const osc = detuned.pop();
        if (osc) {
          osc.stop();
          osc.disconnect();
        }
      }
    },
    setFilterCutoff(hz: number): void {
      droneFilter.frequency.setTargetAtTime(hz, context.currentTime, 0.08);
    },
    setStereoWidth(width: number): void {
      panner.pan.setTargetAtTime(width * 0.7, context.currentTime, 0.08);
      delay.delayTime.setTargetAtTime(0.12 + width * 0.3, context.currentTime, 0.08);
    },
    setClarity(clarity: number): void {
      clarityFilter.frequency.setTargetAtTime(
        90 + clarity * 600,
        context.currentTime,
        0.08,
      );
      droneGain.gain.setTargetAtTime(
        0.02 + clarity * 0.03,
        context.currentTime,
        0.08,
      );
    },
    setMuted(next: boolean): void {
      muted = next;
      if (next && scheduled !== null) {
        window.clearTimeout(scheduled);
        scheduled = null;
      }
    },
    fadeTo(gain: number, durationMs: number): void {
      master.gain.cancelScheduledValues(context.currentTime);
      master.gain.setTargetAtTime(
        gain,
        context.currentTime,
        Math.max(0.02, durationMs / 1000) / 4,
      );
    },
    dispose(): void {
      if (scheduled !== null) {
        window.clearTimeout(scheduled);
        scheduled = null;
      }
      try {
        drone.stop();
      } catch {
        // already stopped
      }
      for (const osc of detuned) {
        try {
          osc.stop();
        } catch {
          // already stopped
        }
        osc.disconnect();
      }
      detuned.length = 0;
      void context.close();
    },
  };

  function schedulePulse(): void {
    if (muted || scheduled !== null) {
      return;
    }
    const osc = context.createOscillator();
    osc.type = "sine";
    osc.frequency.value = 330;
    const env = context.createGain();
    env.gain.setValueAtTime(0.0001, context.currentTime);
    env.gain.exponentialRampToValueAtTime(
      0.05,
      context.currentTime + 0.01,
    );
    env.gain.exponentialRampToValueAtTime(
      0.0001,
      context.currentTime + 0.12,
    );
    osc.connect(env);
    env.connect(pulseGain);
    osc.start();
    osc.stop(context.currentTime + 0.15);
    osc.onended = () => {
      osc.disconnect();
      env.disconnect();
    };
    scheduled = window.setTimeout(() => {
      scheduled = null;
      if (!muted) {
        schedulePulse();
      }
    }, Math.max(80, (1000 / Math.max(0.2, tempoHz)) * 0.5));
  }

  return graph;
}
