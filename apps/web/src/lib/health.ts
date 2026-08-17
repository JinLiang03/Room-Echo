export interface ComponentHealth {
  status: "ok" | "degraded" | "not_implemented" | "error";
  detail: string;
}

export interface HealthResponse {
  status: "ok" | "degraded";
  service: string;
  version: string;
  mode: "mock" | "replay" | "live";
  contracts_version: string;
  components: Record<string, ComponentHealth>;
  checked_at: string;
}

export interface HealthResult {
  ok: boolean;
  response: HealthResponse | null;
  error: string | null;
}

export async function fetchHealth(signal?: AbortSignal): Promise<HealthResult> {
  try {
    const response = await fetch("/healthz", { signal });
    if (!response.ok) {
      return { ok: false, response: null, error: `HTTP ${response.status}` };
    }
    const data = (await response.json()) as HealthResponse;
    return { ok: data.status === "ok", response: data, error: null };
  } catch (error) {
    return {
      ok: false,
      response: null,
      error: error instanceof Error ? error.message : String(error),
    };
  }
}
