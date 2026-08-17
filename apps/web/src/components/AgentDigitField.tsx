import { useEffect, useRef } from "react";
import { hash01, sampleDigitGeometry, segmentsForRole } from "../lib/digit-geometry";

const RAINBOW = ["#e58ba2", "#f0a091", "#cfa952", "#83b8a4", "#8aa8d6", "#a48fdc", "#cf92d9"];

interface Props {
  role: string;
  seed?: string;
  compact?: boolean;
  label?: string;
}

/** A compact, role-specific digit glyph. It is a visual metaphor only. */
export function AgentDigitField({ role, seed = role, compact = false, label }: Props) {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const wrapRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    const wrap = wrapRef.current;
    if (!canvas || !wrap) return;
    const context = canvas.getContext("2d");
    if (!context) return;
    const seedValue = seed.split("").reduce((sum, char) => sum + char.charCodeAt(0), 0);
    const points = sampleDigitGeometry(segmentsForRole(role), compact ? 110 : 180, seedValue + 19);
    let observer: ResizeObserver | null = null;

    const resizeCanvas = () => {
      const rect = wrap.getBoundingClientRect();
      const ratio = Math.min(2, window.devicePixelRatio || 1);
      canvas.width = Math.max(1, Math.round(rect.width * ratio));
      canvas.height = Math.max(1, Math.round(rect.height * ratio));
    };

    const draw = () => {
      const width = canvas.width;
      const height = canvas.height;
      const ratio = Math.min(2, window.devicePixelRatio || 1);
      context.clearRect(0, 0, width, height);
      const scale = Math.min(width, height) * 0.39;
      const centerX = width * 0.5;
      const centerY = height * 0.54;
      const fontSize = Math.max(7 * ratio, Math.min(12 * ratio, Math.min(width, height) / 14));
      context.font = `${fontSize}px ui-monospace, SFMono-Regular, Menlo, Consolas, monospace`;
      context.textAlign = "center";
      context.textBaseline = "middle";
      for (let index = 0; index < points.length; index += 1) {
        const point = points[index];
        const drift = 0;
        const x = centerX + (point.x + drift) * scale;
        const y = centerY - (point.y + drift * 0.4) * scale;
        const alpha = 0.44 + hash01(index, seedValue + 27) * 0.44;
        context.globalAlpha = alpha;
        context.fillStyle = RAINBOW[index % RAINBOW.length];
        context.fillText(point.glyph, x, y);
      }
      context.globalAlpha = 1;
    };

    const resize = () => {
      resizeCanvas();
      draw();
    };
    resize();
    if (typeof ResizeObserver !== "undefined") {
      observer = new ResizeObserver(resize);
      observer.observe(wrap);
    }
    return () => {
      observer?.disconnect();
    };
  }, [compact, role, seed]);

  return (
    <div className={`agent-digit-field${compact ? " agent-digit-field-compact" : ""}`} ref={wrapRef}>
      <canvas
        ref={canvasRef}
        className="agent-digit-canvas"
        role="img"
        aria-label={label ?? `${role} 角色的数字视觉隐喻；不是传感器识别结果`}
      />
    </div>
  );
}
