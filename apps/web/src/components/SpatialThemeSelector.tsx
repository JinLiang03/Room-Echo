import { useEffect, useRef } from "react";
import {
  createThemePoints,
  spatialTheme,
  SPATIAL_THEMES,
  type SpatialThemeId,
} from "../lib/spatial-themes";

const THEME_RAINBOW = ["#ef476f", "#f78c6b", "#e9b949", "#06a77d", "#118ab2", "#6c63ff", "#c445b8"];

interface Props {
  value: SpatialThemeId;
  onChange: (theme: SpatialThemeId) => void;
}

export function SpatialThemeSelector({ value, onChange }: Props) {
  return (
    <section className="theme-selector" aria-labelledby="theme-selector-title">
      <div className="theme-selector-head">
        <div>
          <span className="eyebrow" id="theme-selector-title">
            COLOR FIELD / MOVING GLYPHS
          </span>
          <p>手选一个空间隐喻；所有主题继续读取同一组三项代理信号。</p>
        </div>
        <span className="theme-agent-link">
          视觉隐喻 · {spatialTheme(value).agentRole}
        </span>
      </div>
      <div className="theme-list" role="radiogroup" aria-label="选择数字场视觉主题">
        {SPATIAL_THEMES.map((theme) => (
          <button
            key={theme.id}
            type="button"
            role="radio"
            aria-checked={value === theme.id}
            className={`theme-option ${value === theme.id ? "theme-option-active" : ""}`}
            onClick={() => onChange(theme.id)}
            title={theme.description}
          >
            <ThemePreview theme={theme.id} active={value === theme.id} />
            <span className="theme-option-copy">
              <strong>{theme.label}</strong>
              <small>{theme.name}</small>
            </span>
            <i style={{ background: theme.accent }} aria-hidden="true" />
          </button>
        ))}
      </div>
    </section>
  );
}

function ThemePreview({ theme, active }: { theme: SpatialThemeId; active: boolean }) {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) {
      return;
    }
    const context = canvas.getContext("2d");
    if (!context) {
      return;
    }
    const width = 160;
    const height = 92;
    canvas.width = width * 2;
    canvas.height = height * 2;
    canvas.style.width = `${width}px`;
    canvas.style.height = `${height}px`;
    const points = createThemePoints(theme, 84);
    const reduced = window.matchMedia?.("(prefers-reduced-motion: reduce)")?.matches === true;
    let frame = 0;
    const started = performance.now();
    const draw = (now: number) => {
      const seconds = reduced ? 0 : (now - started) / 1000;
      context.setTransform(2, 0, 0, 2, 0, 0);
      context.clearRect(0, 0, width, height);
      const wash = context.createRadialGradient(width / 2, height / 2, 4, width / 2, height / 2, width * 0.65);
      wash.addColorStop(0, active ? "rgba(255,255,255,0.92)" : "rgba(255,255,255,0.7)");
      wash.addColorStop(1, "rgba(238,243,255,0.32)");
      context.fillStyle = wash;
      context.fillRect(0, 0, width, height);
      context.font = "8px ui-monospace, SFMono-Regular, Menlo, monospace";
      context.textAlign = "center";
      context.textBaseline = "middle";
      for (const [index, point] of points.entries()) {
        const drift = Math.sin(seconds * (0.55 + point.weight * 0.35) + point.phase) * 0.035;
        const x = width / 2 + (point.x + point.z * 0.35 + drift) * 42;
        const y = height * 0.6 + (-point.y + point.z * 0.15 + drift * 0.6) * 36;
        context.globalAlpha = active ? 0.84 : 0.58;
        context.fillStyle = THEME_RAINBOW[(index + Math.floor(seconds * 2)) % THEME_RAINBOW.length];
        context.fillText(point.glyph, x, y);
      }
      context.globalAlpha = 1;
      if (!reduced) frame = window.requestAnimationFrame(draw);
    };
    draw(started);
    return () => window.cancelAnimationFrame(frame);
  }, [active, theme]);

  return (
    <canvas
      ref={canvasRef}
      className="theme-preview"
      aria-hidden="true"
    />
  );
}
