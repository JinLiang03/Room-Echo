import { useCallback, useEffect, useRef } from "react";
import { PERSONAS, personaFor } from "../lib/personas";
import { RAINBOW_COLORS } from "../lib/rainbow";
import type { AgentClaim, CouncilResult, StreamState } from "../lib/types";

interface Props {
  state: StreamState;
  compact?: boolean;
}

const ROLE_ORDER = Object.keys(PERSONAS);

function latestDiscussion(state: StreamState): {
  claims: Map<string, AgentClaim>;
  result: CouncilResult | null;
} {
  const claims = new Map<string, AgentClaim>();
  let result: CouncilResult | null = null;
  for (let index = state.council.order.length - 1; index >= 0; index -= 1) {
    const cycle = state.council.cycles[state.council.order[index]];
    if (!cycle) continue;
    if (!result && cycle.result) result = cycle.result;
    for (const claim of cycle.claims) {
      if (!claims.has(claim.role)) claims.set(claim.role, claim);
    }
  }
  return { claims, result };
}

function voiceFor(
  role: string,
  claim: AgentClaim | undefined,
  result: CouncilResult | null,
): string {
  if (role === "fusion") {
    return result?.headline ?? "等待综合结果";
  }
  return claim?.proposition ?? "等待该视角的证据封存";
}

const DIGIT_GLYPHS = "0123456789";

function roleSalt(role: string): number {
  return [...role].reduce((sum, character) => sum + (character.codePointAt(0) ?? 0), 0);
}

function wrapText(
  context: CanvasRenderingContext2D,
  text: string,
  maxWidth: number,
): string[] {
  const lines: string[] = [];
  let line = "";
  for (const character of [...text]) {
    const candidate = `${line}${character}`;
    if (line && context.measureText(candidate).width > maxWidth) {
      lines.push(line);
      line = character;
    } else {
      line = candidate;
    }
  }
  if (line || lines.length === 0) lines.push(line);
  return lines;
}

/**
 * Draw the accessible Agent claim as a numeric bitmap. The source sentence is
 * only used as a mask; every visible mark is a digit, so the visual reads as
 * words assembled from the sensing field's numeric language.
 */
function DigitText({ text, role }: { text: string; role: string }) {
  const wrapRef = useRef<HTMLSpanElement | null>(null);
  const canvasRef = useRef<HTMLCanvasElement | null>(null);

  const draw = useCallback(() => {
    const wrap = wrapRef.current;
    const canvas = canvasRef.current;
    const context = canvas?.getContext("2d");
    if (!wrap || !canvas || !context) return;

    const rect = wrap.getBoundingClientRect();
    const cssWidth = Math.max(160, rect.width);
    const ratio = Math.min(2, window.devicePixelRatio || 1);
    const fontSize = Math.max(10, Math.min(14, cssWidth / 66));
    const lineHeight = fontSize * 1.75;

    const measure = document.createElement("canvas").getContext("2d");
    if (!measure) return;
    measure.font = `650 ${fontSize}px ui-monospace, SFMono-Regular, Menlo, Consolas, monospace`;
    const lines = wrapText(measure, text, cssWidth - 10);
    const cssHeight = Math.max(28, lines.length * lineHeight + 6);

    wrap.style.height = `${cssHeight}px`;
    canvas.width = Math.max(1, Math.round(cssWidth * ratio));
    canvas.height = Math.max(1, Math.round(cssHeight * ratio));
    canvas.style.width = "100%";
    canvas.style.height = `${cssHeight}px`;

    const mask = document.createElement("canvas");
    mask.width = canvas.width;
    mask.height = canvas.height;
    const maskContext = mask.getContext("2d");
    if (!maskContext) return;

    maskContext.scale(ratio, ratio);
    maskContext.fillStyle = "#ffffff";
    maskContext.font = measure.font;
    maskContext.textBaseline = "top";
    lines.forEach((line, index) => {
      maskContext.fillText(line, 5, 2 + index * lineHeight);
    });

    context.setTransform(ratio, 0, 0, ratio, 0, 0);
    context.clearRect(0, 0, cssWidth, cssHeight);
    context.font = `650 ${Math.max(7, fontSize * 0.76)}px ui-monospace, SFMono-Regular, Menlo, Consolas, monospace`;
    context.textAlign = "center";
    context.textBaseline = "middle";
    const pixels = maskContext.getImageData(0, 0, mask.width, mask.height).data;
    const sampleStep = Math.max(2, Math.round(fontSize * 0.3));
    const salt = roleSalt(role);
    let pointIndex = 0;
    for (let y = 2; y < cssHeight; y += sampleStep) {
      for (let x = 2; x < cssWidth; x += sampleStep) {
        const pixelX = Math.min(mask.width - 1, Math.round(x * ratio));
        const pixelY = Math.min(mask.height - 1, Math.round(y * ratio));
        const alpha = pixels[(pixelY * mask.width + pixelX) * 4 + 3];
        if (alpha < 110) continue;
        context.globalAlpha = 0.78 + ((pointIndex + salt) % 4) * 0.05;
        context.fillStyle = RAINBOW_COLORS[(pointIndex + salt) % RAINBOW_COLORS.length];
        context.fillText(DIGIT_GLYPHS[(salt + pointIndex * 13) % DIGIT_GLYPHS.length], x, y);
        pointIndex += 1;
      }
    }
    context.globalAlpha = 1;
  }, [role, text]);

  useEffect(() => {
    const wrap = wrapRef.current;
    if (!wrap) return;
    draw();
    if (typeof ResizeObserver === "undefined") return;
    const observer = new ResizeObserver(draw);
    observer.observe(wrap);
    return () => observer.disconnect();
  }, [draw]);

  return (
    <span
      ref={wrapRef}
      className={`voice-letters voice-digit-word voice-digit-word-${role}`}
      aria-label={text}
      role="img"
    >
      <canvas ref={canvasRef} className="voice-digit-canvas" aria-hidden="true" />
    </span>
  );
}

export function AgentVoiceRiver({ state, compact = false }: Props) {
  const { claims, result } = latestDiscussion(state);
  const stale = state.stale || state.connection !== "online";

  return (
    <section
      className={`agent-voice-river${compact ? " agent-voice-river-compact" : ""}`}
      aria-label="七个 Agent 实时观点"
    >
      <header className="agent-voice-head">
        <div>
          <span className="agent-voice-kicker">SEVEN AGENTS / LIVE VOICES</span>
          <h2>七个视角正在读同一组证据</h2>
        </div>
        <span className={`agent-voice-state${stale ? " is-stale" : ""}`}>
          {stale ? "等待新的证据周期" : "观点随封存周期更新"}
        </span>
      </header>
      <div className="agent-voice-grid">
        {ROLE_ORDER.map((role, index) => {
          const persona = personaFor(role);
          const claim = claims.get(role);
          const text = voiceFor(role, claim, result);
          return (
            <article
              className={`agent-voice-item agent-voice-${role}`}
              data-agent-index={index + 1}
              key={role}
            >
              <div className="agent-voice-mark" aria-hidden="true">
                <span>{String(index + 1).padStart(2, "0")}</span>
              </div>
              <div className="agent-voice-copy">
                <div className="agent-voice-name">
                  <strong>{persona.name}</strong>
                  <span>{role}</span>
                </div>
                <p className={claim || role === "fusion" ? "has-voice" : "is-placeholder"}>
                  <DigitText text={text} role={role} />
                </p>
                {claim && <small>{claim.stance} · {claim.state}</small>}
              </div>
            </article>
          );
        })}
      </div>
      <p className="agent-voice-boundary">
        彩色数字是 Agent 的文字观点视觉化，不是 CSI 原始值，也不是现场物体识别。
      </p>
    </section>
  );
}
