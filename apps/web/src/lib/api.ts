import type { SimulatedCareScenario } from "../generated/contracts";
import type { ReplayBundleSummary, SessionStatus } from "./types";

const BASE = "/api";

export async function fetchBundles(): Promise<ReplayBundleSummary[]> {
  const response = await fetch(`${BASE}/replay/bundles`, {
    headers: { Accept: "application/json" },
  });
  if (!response.ok) {
    throw new Error(`list bundles failed: ${response.status}`);
  }
  return (await response.json()) as ReplayBundleSummary[];
}

export async function fetchCareScenario(
  moment: SimulatedCareScenario["selected_moment"] = "bathroom_timeout",
  signal?: AbortSignal,
): Promise<SimulatedCareScenario> {
  const response = await fetch(
    `${BASE}/care/scenario?moment=${encodeURIComponent(moment)}`,
    {
      headers: { Accept: "application/json" },
      signal,
    },
  );
  if (!response.ok) {
    throw new Error(`care scenario failed: ${response.status}`);
  }
  return (await response.json()) as SimulatedCareScenario;
}

export async function startStream(bundleId: string): Promise<SessionStatus> {
  const response = await fetch(
    `${BASE}/stream/start?bundle_id=${encodeURIComponent(bundleId)}`,
    { method: "POST" },
  );
  if (!response.ok) {
    const body = (await response.json().catch(() => null)) as { detail?: string } | null;
    throw new Error(body?.detail ?? `start stream failed: ${response.status}`);
  }
  return (await response.json()) as SessionStatus;
}

export async function controlStream(action: string, payload?: Record<string, unknown>): Promise<SessionStatus> {
  const response = await fetch(`${BASE}/stream/control`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ action, ...payload }),
  });
  if (!response.ok) {
    throw new Error(`control ${action} failed: ${response.status}`);
  }
  return (await response.json()) as SessionStatus;
}

export async function stopStream(): Promise<SessionStatus> {
  const response = await fetch(`${BASE}/stream/stop`, { method: "POST" });
  if (!response.ok) {
    throw new Error(`stop stream failed: ${response.status}`);
  }
  return (await response.json()) as SessionStatus;
}

export function wsUrl(): string {
  const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
  return `${protocol}//${window.location.host}/ws`;
}
