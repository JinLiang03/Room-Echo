import type { CouncilResult, SignalTriplet } from "./types";

export function pct(value: number | undefined | null, digits = 0): string {
  if (value === undefined || value === null || Number.isNaN(value)) {
    return "—";
  }
  return `${(value * 100).toFixed(digits)}%`;
}

export function num(value: number | undefined | null, digits = 2): string {
  if (value === undefined || value === null || Number.isNaN(value)) {
    return "—";
  }
  return value.toFixed(digits);
}

export function ageSeconds(ts: number | null, now = Date.now()): number | null {
  if (ts === null) {
    return null;
  }
  return Math.max(0, (now - ts) / 1000);
}

export function freshnessLabel(ts: number | null, now = Date.now()): string {
  const age = ageSeconds(ts, now);
  if (age === null) {
    return "无数据";
  }
  if (age < 2) {
    return "实时";
  }
  if (age < 10) {
    return `${age.toFixed(1)}s 前`;
  }
  return "已过期";
}

export function shortHash(hash: string | undefined | null, len = 12): string {
  if (!hash) {
    return "—";
  }
  return hash.length > len ? `${hash.slice(0, len)}…` : hash;
}

export function formatSeconds(s: number | undefined | null): string {
  if (s === undefined || s === null || Number.isNaN(s)) {
    return "0.0s";
  }
  return `${s.toFixed(1)}s`;
}

export function stateLabel(
  value: string | undefined | null,
  fallback = "unknown",
): string {
  return value || fallback;
}

export function tripletStatus(triplet: SignalTriplet | null): string {
  return triplet?.status ?? "unknown";
}

export function councilStatusLabel(result: CouncilResult | null): string {
  if (!result) {
    return "讨论不可用";
  }
  if (result.status === "supported") {
    return "supported";
  }
  if (result.status === "ambiguous") {
    return "ambiguous";
  }
  return "unavailable";
}

export function agreementText(result: CouncilResult | null): string {
  if (!result) {
    return "—";
  }
  const agreement = result.interpretation_agreement;
  return `${agreement.supporting} 项主张一致，${agreement.contradicting} 项分歧，${agreement.unresolved_challenges} 项未解决`;
}
