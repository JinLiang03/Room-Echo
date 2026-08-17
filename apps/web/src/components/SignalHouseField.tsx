import { useEffect, useRef } from "react";
import { mapRenderParams, type RenderParams } from "../lib/multimodal";
import { HOUSE_SEGMENTS, sampleDigitGeometry } from "../lib/digit-geometry";
import type { CouncilResult, SignalTriplet } from "../lib/types";

const RAINBOW = ["#e58ba2", "#f0a091", "#cfa952", "#83b8a4", "#8aa8d6", "#a48fdc", "#cf92d9"];

interface Props {
  triplet: SignalTriplet | null;
  result: CouncilResult | null;
  stale: boolean;
  reducedMotion?: boolean;
  debug?: boolean;
}

/** A stable house-shaped signal field; it is a chosen visual metaphor, not house detection. */
export function SignalHouseField({
  triplet,
  result,
  stale,
  reducedMotion = false,
  debug = false,
}: Props) {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const wrapRef = useRef<HTMLDivElement | null>(null);
  const paramsRef = useRef<RenderParams>(mapRenderParams({ triplet, result, stale }));
  paramsRef.current = mapRenderParams({ triplet, result, stale });

  useEffect(() => {
    const canvas = canvasRef.current;
    const wrap = wrapRef.current;
    if (!canvas || !wrap) return;
    const context = canvas.getContext("2d");
    if (!context) return;
    const mediaReduced =
      window.matchMedia?.("(prefers-reduced-motion: reduce)")?.matches === true;
    const staticMode = reducedMotion || mediaReduced;
    const points = sampleDigitGeometry(HOUSE_SEGMENTS, 520, 0x484f4d45);
    let frameId = 0;
    let observer: ResizeObserver | null = null;

    const resizeCanvas = () => {
      const rect = wrap.getBoundingClientRect();
      const ratio = Math.min(2, window.devicePixelRatio || 1);
      canvas.width = Math.max(1, Math.round(rect.width * ratio));
      canvas.height = Math.max(1, Math.round(rect.height * ratio));
    };

    const draw = (now: number) => {
      const width = canvas.width;
      const height = canvas.height;
      const ratio = Math.min(2, window.devicePixelRatio || 1);
      const params = paramsRef.current;
      const seconds = staticMode ? 0 : now / 1000;
      const highContrast = document.documentElement.classList.contains("high-contrast");
      context.clearRect(0, 0, width, height);
      context.fillStyle = highContrast ? "#05070a" : "rgba(255, 255, 255, 0)";
      context.fillRect(0, 0, width, height);

      const scale = Math.min(width * 0.37, height * 0.42);
      const centerX = width * 0.5;
      const centerY = height * 0.55;
      const motion = Math.min(1, Math.max(0, (params.particle_speed - 0.08) / 1.72));
      const density = params.active ? 0.52 + params.field_density * 0.48 : 0.62;
      const depth = params.z_layer_separation;
      const fontSize = Math.max(8 * ratio, Math.min(13 * ratio, Math.min(width, height) / 18));
      context.font = `${fontSize}px ui-monospace, SFMono-Regular, Menlo, Consolas, monospace`;
      context.textAlign = "center";
      context.textBaseline = "middle";

      for (let index = 0; index < points.length; index += 1) {
        if (index / points.length > density) continue;
        const point = points[index];
        const wave = staticMode ? 0 : Math.sin(seconds * (0.5 + motion) + point.phase) * 0.012;
        const layer = point.z * depth * 0.12;
        const x = centerX + (point.x + layer + wave) * scale;
        const y = centerY - (point.y + wave * 0.35) * scale;
        const alpha = params.active ? 0.35 + params.saturation * 0.55 : 0.62;
        context.globalAlpha = Math.max(0.16, alpha * (0.72 + (index % 5) * 0.06));
        context.fillStyle = highContrast ? "#9fc2ff" : RAINBOW[(index + Math.floor(seconds * 1.4)) % RAINBOW.length];
        context.fillText(params.active ? point.glyph : index % 3 === 0 ? "0" : "·", x, y);
      }
      context.globalAlpha = 1;
      context.strokeStyle = highContrast ? "rgba(159,194,255,.24)" : "rgba(17,138,178,.12)";
      context.lineWidth = ratio;
      context.setLineDash([4 * ratio, 8 * ratio]);
      context.beginPath();
      context.moveTo(centerX - scale * 0.9, centerY + scale * 0.62);
      context.lineTo(centerX + scale * 0.9, centerY + scale * 0.62);
      context.stroke();
      context.setLineDash([]);

      if (debug) {
        context.fillStyle = highContrast ? "#9fc2ff" : "#172047";
        context.font = `${10 * ratio}px ui-monospace, SFMono-Regular, Menlo, Consolas, monospace`;
        context.fillText(`${params.reason} · ${Math.round(density * 100)}%`, width - 84 * ratio, height - 12 * ratio);
      }
      if (!staticMode && document.visibilityState !== "hidden") {
        frameId = window.requestAnimationFrame(draw);
      }
    };

    const resize = () => {
      resizeCanvas();
      draw(performance.now());
    };
    resize();
    if (typeof ResizeObserver !== "undefined") {
      observer = new ResizeObserver(resize);
      observer.observe(wrap);
    }
    if (!staticMode) frameId = window.requestAnimationFrame(draw);
    return () => {
      window.cancelAnimationFrame(frameId);
      observer?.disconnect();
    };
  }, [debug, reducedMotion]);

  return (
    <div className="signal-house-field signal-sculpture" ref={wrapRef}>
      <canvas
        ref={canvasRef}
        className="signal-house-canvas sculpture-canvas"
        role="img"
        aria-label="数字构成的房屋视觉主题；实时信号只改变密度、速度与层次，不表示检测到真实房屋"
      />
      <div className="signal-house-label" aria-hidden="true">
        <span>HOUSE / DIGIT STUDY</span>
        <span>{stale ? "UNKNOWN · STATIC PREVIEW" : "INFERENCE FIELD · NOT A CAMERA IMAGE"}</span>
      </div>
    </div>
  );
}
