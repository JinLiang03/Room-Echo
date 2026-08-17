import { useEffect, useRef, useState } from "react";
import {
  mapRenderParams,
  renderSnapshotHash,
  seedParticles,
  VISUAL_SEED,
  type Particle,
  type RenderParams,
} from "../lib/multimodal";
import type { CouncilResult, SignalTriplet } from "../lib/types";
import { measureFrameTiming } from "../lib/frame-timing";

interface Props {
  triplet: SignalTriplet | null;
  result: CouncilResult | null;
  stale: boolean;
  reducedMotion?: boolean;
  debug?: boolean;
  particleCount?: number;
  onStats?: (stats: Stats) => void;
}

interface Stats {
  fps: number;
  drawCalls: number;
  dropped: number;
}

/**
 * Deterministic abstract "radio interference field".
 * No silhouettes, floor plans, thermal humans, eyes, or camera framing —
 * only seeded particles, rings, and translucent layers driven by approved
 * render parameters. Unknown/stale collapses the field to a dim static state.
 */
export function SignalSculpture({
  triplet,
  result,
  stale,
  reducedMotion = false,
  debug = false,
  particleCount = 150,
  onStats,
}: Props) {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const wrapRef = useRef<HTMLDivElement | null>(null);
  const paramsRef = useRef<RenderParams>(
    mapRenderParams({ triplet, result, stale }),
  );
  const particlesRef = useRef<Particle[]>(seedParticles(VISUAL_SEED, particleCount));
  const activityRef = useRef(0);
  const statsRef = useRef<Stats>({ fps: 0, drawCalls: 0, dropped: 0 });
  const redrawRef = useRef<(() => void) | null>(null);
  const [stats, setStats] = useState<Stats>({ fps: 0, drawCalls: 0, dropped: 0 });
  const [snapshotHash, setSnapshotHash] = useState("");

  paramsRef.current = mapRenderParams({ triplet, result, stale });

  useEffect(() => {
    const canvas = canvasRef.current;
    const wrap = wrapRef.current;
    if (!canvas || !wrap) {
      return;
    }
    let context: CanvasRenderingContext2D | null = null;
    try {
      context = canvas.getContext("2d");
    } catch {
      context = null;
    }
    if (!context) {
      return;
    }
    let frame = 0;
    let last = performance.now();
    let fpsEma = 60;
    let dropped = 0;
    const staticMode =
      reducedMotion ||
      window.matchMedia?.("(prefers-reduced-motion: reduce)")?.matches === true;
    let frameId = 0;

    const draw = (now: number) => {
      const timing = measureFrameTiming(now - last, fpsEma);
      last = now;
      fpsEma = timing.fpsEma;
      if (timing.dropped) {
        dropped += 1;
      }
      statsRef.current = {
        fps: Math.round(fpsEma),
        drawCalls: drawFrame(
          context,
          canvas,
          paramsRef.current,
          particlesRef.current,
          activityRef,
          staticMode ? 0 : now / 1000,
          staticMode ? 1 : timing.simulationDtMs / 1000,
        ),
        dropped,
      };
      onStats?.(statsRef.current);
      if (debug && frame % 30 === 0) {
        setStats({ ...statsRef.current });
        setSnapshotHash(
          renderSnapshotHash(paramsRef.current, particlesRef.current),
        );
      }
      frame += 1;
      if (!staticMode) {
        frameId = window.requestAnimationFrame(draw);
      }
    };

    const requestStaticDraw = () => {
      if (!staticMode) {
        return;
      }
      draw(performance.now());
    };
    redrawRef.current = requestStaticDraw;

    const resize = () => {
      const rect = wrap.getBoundingClientRect();
      const ratio = window.devicePixelRatio || 1;
      canvas.width = Math.max(1, Math.round(rect.width * ratio));
      canvas.height = Math.max(1, Math.round(rect.height * ratio));
      requestStaticDraw();
    };
    resize();
    let observer: ResizeObserver | null = null;
    if (typeof ResizeObserver !== "undefined") {
      observer = new ResizeObserver(resize);
      observer.observe(wrap);
    }

    if (!staticMode) {
      frameId = window.requestAnimationFrame(draw);
    }
    return () => {
      redrawRef.current = null;
      window.cancelAnimationFrame(frameId);
      observer?.disconnect();
    };
  }, [debug, onStats, reducedMotion]);

  useEffect(() => {
    redrawRef.current?.();
  }, [triplet, result, stale, reducedMotion]);

  return (
    <div className="signal-sculpture" ref={wrapRef} aria-label="抽象无线电干涉场">
      <canvas
        ref={canvasRef}
        className="sculpture-canvas"
        role="img"
        aria-label="抽象无线电干涉场,非真实影像"
      />
      <div className="sculpture-meta">
        <span>soft volume / 7 depth layers</span>
        <span>mapping {paramsRef.current.mapping_version}</span>
        <span>data rate {paramsRef.current.data_rate_hz.toFixed(1)} Hz</span>
        <span className={`sculpture-state ${paramsRef.current.active ? "" : "sculpture-idle"}`}>
          {paramsRef.current.reason}
        </span>
      </div>
      {debug && (
        <div className="sculpture-debug" aria-label="渲染调试信息">
          <span>fps {stats.fps}</span>
          <span>draws {stats.drawCalls}</span>
          <span>dropped {stats.dropped}</span>
          <span>hash {snapshotHash}</span>
        </div>
      )}
    </div>
  );
}

function drawFrame(
  context: CanvasRenderingContext2D,
  canvas: HTMLCanvasElement,
  params: RenderParams,
  particles: Particle[],
  activityRef: { current: number },
  seconds: number,
  dt: number,
): number {
  const width = canvas.width;
  const height = canvas.height;
  const cx = width / 2;
  const cy = height / 2;
  const maxR = Math.min(width, height) * 0.42;

  // Activity eases toward 1 (active) or 0 (stale/unknown) — clears residue.
  const target = params.active ? 1 : 0;
  activityRef.current += (target - activityRef.current) * Math.min(1, dt * 3);
  const activity = activityRef.current;

  let draws = 0;
  context.clearRect(0, 0, width, height);
  draws += 1;

  const saturation = lerpChannel(params.saturation, activity);
  const diffusion = params.edge_diffusion * activity;

  // Depth layers: concentric translucent rings; separation from z proxy.
  const layers = 4;
  context.save();
  for (let layer = 0; layer < layers; layer += 1) {
    const radius = maxR * (0.28 + 0.2 * layer + params.z_layer_separation * 0.16);
    const alpha = (0.06 + 0.05 * layer) * activity;
    context.beginPath();
    context.arc(cx, cy, Math.max(2, radius), 0, Math.PI * 2);
    context.strokeStyle = `hsla(${215 + layer * 18}, ${saturation * 80}%, 65%, ${alpha})`;
    context.lineWidth = 1 + layer * 0.4;
    context.shadowBlur = diffusion * 12;
    context.shadowColor = "rgba(59,130,246,0.35)";
    context.stroke();
    draws += 1;
  }
  context.restore();

  // Disagreement: two thin phase rings offset by disagreement_phase only.
  if (params.disagreement_phase > 0.01 && activity > 0.05) {
    context.save();
    const baseAngle = seconds * 0.25;
    const phase = params.disagreement_phase;
    context.strokeStyle = `hsla(${172}, ${saturation * 70}%, 68%, ${0.28 * activity})`;
    context.lineWidth = 1.2;
    for (const offset of [0, Math.PI]) {
      context.beginPath();
      context.arc(
        cx,
        cy,
        maxR * (0.42 + phase * 0.12),
        baseAngle + offset,
        baseAngle + offset + Math.PI * 0.55,
      );
      context.stroke();
      draws += 1;
    }
    context.restore();
  }

  // A soft perspective volume gives Story a spatial body without implying a
  // room scan: translucent planes and ribs are only an inference-field aid.
  draws += drawVolumetricField(
    context,
    width,
    cx,
    cy,
    maxR,
    params,
    seconds,
    activity,
  );

  // Particle field: deterministic bases; time only advances motion.
  const pulse = Math.sin(seconds * Math.PI * 2 * params.pulse_hz);
  const speed = params.particle_speed * activity;
  const densityAlpha = 0.12 + params.field_density * 0.5;
  context.textAlign = "center";
  context.textBaseline = "middle";
  context.font = `${Math.max(8, Math.min(14, maxR / 34))}px ui-monospace, SFMono-Regular, Menlo, Consolas, monospace`;
  for (const particle of particles) {
    const travel =
      (seconds * speed * particle.speedFactor + particle.phase) % (Math.PI * 2);
    const radius = maxR * (0.05 + 0.8 * particle.radius) * (1 + 0.08 * pulse);
    const x = cx + Math.cos(particle.angle + travel * 0.4) * radius;
    const y = cy + Math.sin(particle.angle + travel * 0.4) * radius * 0.82;
    const size = particle.size * (0.7 + 0.5 * activity);
    context.beginPath();
    context.fillStyle = `hsla(${particle.hue}, ${saturation * 85}%, 72%, ${densityAlpha * activity})`;
    context.globalAlpha = Math.min(1, densityAlpha * activity + size * 0.04);
    context.fillText(String((particle.index * 7 + Math.floor(seconds * 0.4)) % 10), x, y);
    context.globalAlpha = 1;
    draws += 1;
  }

  // Static dim haze for stale/unknown: no motion, low saturation. Keep a
  // deterministic radial falloff so the canvas remains visibly rendered
  // without implying a scene or carrying residue from the previous state.
  context.save();
  const haze = context.createRadialGradient(cx, cy, 0, cx, cy, maxR * 1.7);
  const hazeAlpha = 0.16 * (1 - activity);
  haze.addColorStop(0, `hsla(222, 18%, 48%, ${hazeAlpha})`);
  haze.addColorStop(0.62, `hsla(222, 14%, 38%, ${hazeAlpha * 0.62})`);
  haze.addColorStop(1, `hsla(222, 10%, 28%, ${hazeAlpha * 0.22})`);
  context.fillStyle = haze;
  context.fillRect(0, 0, width, height);
  context.restore();
  draws += 1;

  return draws;
}

function drawVolumetricField(
  context: CanvasRenderingContext2D,
  width: number,
  cx: number,
  cy: number,
  maxR: number,
  params: RenderParams,
  seconds: number,
  activity: number,
): number {
  if (activity <= 0.01) return 0;
  let draws = 0;
  const lineWidth = Math.max(1, Math.min(2.2, width / 720));
  const layers = 7;
  const depthLift = params.z_layer_separation * maxR * 0.16;

  context.save();
  context.lineWidth = lineWidth;
  for (let layer = 0; layer < layers; layer += 1) {
    const t = layer / (layers - 1);
    const halfWidth = maxR * (0.28 + t * 0.78);
    const top = cy - maxR * (0.66 - t * 0.12) - depthLift * (1 - t);
    const bottom = cy + maxR * (0.04 + t * 0.5);
    const skew = maxR * (0.14 + t * 0.26);
    const hue = 174 + layer * 22;
    context.strokeStyle = `hsla(${hue}, ${45 + params.saturation * 35}%, 62%, ${0.08 + activity * 0.1})`;
    context.beginPath();
    context.moveTo(cx - halfWidth + skew, top);
    context.lineTo(cx + halfWidth + skew, top);
    context.lineTo(cx + halfWidth - skew, bottom);
    context.lineTo(cx - halfWidth - skew, bottom);
    context.closePath();
    context.stroke();
    draws += 1;
  }

  for (let rib = -3; rib <= 3; rib += 1) {
    const u = rib / 3;
    context.strokeStyle = `hsla(${198 + (rib + 3) * 11}, 58%, 66%, ${0.08 + activity * 0.1})`;
    context.beginPath();
    context.moveTo(cx + u * maxR * 0.46, cy - maxR * 0.66 - depthLift);
    context.lineTo(cx + u * maxR * 1.18, cy + maxR * 0.54);
    context.stroke();
    draws += 1;
  }
  context.restore();

  // Low-alpha ellipses make the volume legible as a soft field rather than a
  // flat ring. Their drift is presentation-only and does not alter signal data.
  for (let blob = 0; blob < 4; blob += 1) {
    const drift = Math.sin(seconds * (0.18 + blob * 0.04) + blob) * maxR * 0.08;
    const x = cx + (blob - 1.5) * maxR * 0.28 + drift;
    const y = cy - maxR * 0.08 + Math.cos(seconds * 0.2 + blob) * maxR * 0.08;
    const radius = maxR * (0.22 + blob * 0.035);
    const gradient = context.createRadialGradient(x, y, 0, x, y, radius);
    const hue = 188 + blob * 28;
    gradient.addColorStop(0, `hsla(${hue}, 68%, 72%, ${0.1 * activity})`);
    gradient.addColorStop(1, `hsla(${hue}, 55%, 62%, 0)`);
    context.save();
    context.fillStyle = gradient;
    context.translate(x, y);
    context.scale(1.4, 0.48);
    context.beginPath();
    context.arc(0, 0, radius, 0, Math.PI * 2);
    context.fill();
    context.restore();
    draws += 1;
  }
  return draws;
}

function lerpChannel(saturation: number, activity: number): number {
  return Math.min(1, Math.max(0, saturation * (0.25 + 0.75 * activity)));
}
