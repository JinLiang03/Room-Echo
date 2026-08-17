import { useEffect, useRef } from "react";
import { hash01, sampleDigitGeometry, segmentsForRole } from "../lib/digit-geometry";

const RAINBOW = ["#ef476f", "#f78c6b", "#e9b949", "#06a77d", "#118ab2", "#6c63ff", "#c445b8"];

interface Props {
  role?: string;
  seed?: string;
  label?: string;
  size?: "small" | "medium";
}

/** A tiny static numeric mark used as the visual punctuation for section titles. */
export function DigitSectionMark({
  role = "fusion",
  seed = role,
  label,
  size = "small",
}: Props) {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const wrapRef = useRef<HTMLSpanElement | null>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    const wrap = wrapRef.current;
    const context = canvas?.getContext("2d");
    if (!canvas || !wrap || !context) return;

    const seedValue = seed.split("").reduce((sum, char) => sum + char.charCodeAt(0), 0);
    const points = sampleDigitGeometry(
      segmentsForRole(role),
      size === "medium" ? 26 : 18,
      seedValue + 73,
    );

    const draw = () => {
      const rect = wrap.getBoundingClientRect();
      const ratio = Math.min(2, window.devicePixelRatio || 1);
      canvas.width = Math.max(1, Math.round(rect.width * ratio));
      canvas.height = Math.max(1, Math.round(rect.height * ratio));
      const width = canvas.width;
      const height = canvas.height;
      const scale = Math.min(width, height) * 0.4;
      const fontSize = Math.max(
        5.5 * ratio,
        Math.min(8 * ratio, Math.min(width, height) / 6.2),
      );
      context.clearRect(0, 0, width, height);
      context.font = `${fontSize}px ui-monospace, SFMono-Regular, Menlo, Consolas, monospace`;
      context.textAlign = "center";
      context.textBaseline = "middle";
      for (let index = 0; index < points.length; index += 1) {
        const point = points[index];
        context.globalAlpha = 0.42 + hash01(index, seedValue + 91) * 0.5;
        context.fillStyle = RAINBOW[index % RAINBOW.length];
        context.fillText(point.glyph, width * 0.5 + point.x * scale, height * 0.52 - point.y * scale);
      }
      context.globalAlpha = 1;
    };

    draw();
    let observer: ResizeObserver | null = null;
    if (typeof ResizeObserver !== "undefined") {
      observer = new ResizeObserver(draw);
      observer.observe(wrap);
    }
    return () => observer?.disconnect();
  }, [role, seed, size]);

  return (
    <span
      ref={wrapRef}
      className={`digit-section-mark digit-section-mark-${size}`}
      aria-label={label}
      role={label ? "img" : undefined}
    >
      <canvas ref={canvasRef} aria-hidden={label ? undefined : true} />
    </span>
  );
}
