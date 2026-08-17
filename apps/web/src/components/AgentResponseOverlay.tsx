import type { CSSProperties } from "react";
import type { AgentClaim, CouncilResult, CycleView, StreamState } from "../lib/types";

const ROLE_COLORS = {
  architecture: "#315efb",
  biota: "#10a37f",
  feng_shui: "#d59b00",
  psyche: "#f05a4f",
  soundscape: "#38bdf8",
  skeptic: "#dc6b2f",
  fusion: "#7c3aed",
} as const;

type OverlayRole = keyof typeof ROLE_COLORS;

interface OverlayPulse {
  role: OverlayRole;
  revision: string;
  effect: NonNullable<CouncilResult["life_interaction"]>["effect"];
  sound: NonNullable<CouncilResult["sound_motion"]> | null;
}

export function AgentResponseOverlay({
  state,
  reducedMotion,
}: {
  state: StreamState;
  reducedMotion: boolean;
}) {
  const pulse = latestPulse(state);
  if (!pulse || state.stale) return null;
  const responseDigits = createResponseCloud(pulse.role);
  return (
    <div
      aria-hidden="true"
      className={`agent-response-overlay agent-response-${pulse.role} agent-effect-${pulse.effect} ${soundClass(pulse.sound)}${
        reducedMotion ? " is-static" : ""
      }`}
      data-agent-effect="colour-and-response-only"
      data-measurement-mutation="none"
      data-response-effect={pulse.effect}
      data-sound-rhythm={pulse.sound?.rhythm ?? "unknown"}
      data-sound-synchrony={pulse.sound?.synchrony ?? "unknown"}
      key={pulse.revision}
      style={overlayStyle(pulse)}
    >
      {responseDigits.map((digit, index) => (
        <span
          aria-hidden="true"
          className="agent-response-digit"
          key={`${digit.glyph}-${index}`}
          style={responseDigitStyle(digit.x, digit.y, digit.rotation, index)}
        >
          {digit.glyph}
        </span>
      ))}
    </div>
  );
}

function latestPulse(state: StreamState): OverlayPulse | null {
  for (let index = state.council.order.length - 1; index >= 0; index -= 1) {
    const cycle = state.council.cycles[state.council.order[index]];
    if (!cycle) continue;
    const pulse = pulseForCycle(cycle);
    if (pulse) return pulse;
  }
  return null;
}

function pulseForCycle(cycle: CycleView): OverlayPulse | null {
  if (cycle.result) {
    return {
      role: "fusion",
      revision: `${cycle.result.cycle_id}:${cycle.result.provenance.generated_at}`,
      effect: cycle.result.life_interaction?.effect ?? "echo",
      sound: cycle.result.sound_motion ?? null,
    };
  }
  const rejected = new Set(cycle.rejections.map((item) => item.target_id));
  const challenge = [...cycle.challenges]
    .reverse()
    .find((item) => !rejected.has(item.challenge_id));
  if (challenge) {
    return {
      role: "skeptic",
      revision: challenge.challenge_id,
      effect: challenge.assessment?.withhold_judgment ? "hold" : "verify",
      sound: null,
    };
  }
  const claim = [...cycle.claims]
    .reverse()
    .find((item) => isOverlayRole(item.role) && !rejected.has(item.claim_id));
  if (!claim) return null;
  const role = claim.role as OverlayRole;
  return {
    role,
    revision: `${claim.claim_id}:${claim.state}`,
    effect: claim.presentation?.effect ?? fallbackEffect(role),
    sound: null,
  };
}

function isOverlayRole(role: AgentClaim["role"]): role is OverlayRole {
  return role in ROLE_COLORS;
}

function fallbackEffect(
  role: OverlayRole,
): NonNullable<CouncilResult["life_interaction"]>["effect"] {
  const effects = {
    architecture: "contract",
    biota: "recover",
    feng_shui: "surge",
    psyche: "float",
    soundscape: "hold",
    skeptic: "verify",
    fusion: "echo",
  } as const;
  return effects[role];
}

function soundClass(sound: NonNullable<CouncilResult["sound_motion"]> | null): string {
  if (!sound) return "sound-rhythm-unknown sound-sync-unknown";
  const rhythm = {
    停顿: "pause",
    缓拍: "slow",
    稳拍: "steady",
    急拍: "fast",
    未知: "unknown",
  }[sound.rhythm];
  const synchrony = {
    松散: "loose",
    部分同步: "partial",
    同步: "locked",
    未知: "unknown",
  }[sound.synchrony];
  return `sound-rhythm-${rhythm} sound-sync-${synchrony}`;
}

function overlayStyle(pulse: OverlayPulse): CSSProperties {
  const sound = pulse.sound;
  const duration = {
    停顿: "4.8s",
    缓拍: "3.2s",
    稳拍: "2.2s",
    急拍: "1.05s",
    未知: "3.8s",
  }[sound?.rhythm ?? "未知"];
  const size = {
    近: "0.72",
    中: "1",
    远: "1.28",
    未知: "1",
  }[sound?.distance ?? "未知"];
  const weight = {
    薄: "1px",
    中: "2px",
    厚: "4px",
    未知: "1px",
  }[sound?.thickness ?? "未知"];
  const brightness = {
    低: "0.52",
    中: "0.72",
    高: "1",
    未知: "0.46",
  }[sound?.pitch ?? "未知"];
  return {
    "--agent-response-color": ROLE_COLORS[pulse.role],
    "--agent-response-duration": duration,
    "--agent-response-size": size,
    "--agent-response-weight": weight,
    "--agent-response-brightness": brightness,
  } as CSSProperties;
}

function responseDigitStyle(
  x: number,
  y: number,
  rotation: number,
  index: number,
): CSSProperties {
  return {
    "--response-x": `${Math.round(x * 18)}%`,
    "--response-y": `${Math.round(y * 13)}%`,
    "--response-angle": `${Math.round((rotation * 180) / Math.PI)}deg`,
    "--response-delay": `${index * 45}ms`,
  } as CSSProperties;
}

function createResponseCloud(role: OverlayRole): Array<{
  glyph: string;
  x: number;
  y: number;
  rotation: number;
}> {
  const seed = role.length * 11;
  const offsets = [
    [-0.22, -0.08, -12],
    [0.11, -0.18, 18],
    [0.25, 0.05, -7],
    [-0.08, 0.19, 11],
    [0.04, 0.02, -22],
    [-0.24, 0.16, 9],
  ] as const;
  return offsets.map(([x, y, rotation], index) => ({
    glyph: String((seed + index * 7) % 10),
    x,
    y,
    rotation,
  }));
}
