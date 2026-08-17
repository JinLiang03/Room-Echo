import { describe, expect, it, vi } from "vitest";
import { fetchHealth } from "./health";

const HEALTHY_PAYLOAD = {
  status: "ok",
  service: "wifi-spatial-council-api",
  version: "0.1.0",
  mode: "mock",
  contracts_version: "1.0.0",
  components: {
    api: { status: "ok", detail: "http service healthy" },
    contracts: { status: "ok", detail: "schemas validated" },
  },
  checked_at: "2026-08-06T00:00:00Z",
};

describe("fetchHealth", () => {
  it("parses a healthy payload", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        status: 200,
        json: async () => HEALTHY_PAYLOAD,
      }),
    );
    const result = await fetchHealth();
    expect(result.ok).toBe(true);
    expect(result.response?.mode).toBe("mock");
    expect(result.response?.contracts_version).toBe("1.0.0");
    vi.unstubAllGlobals();
  });

  it("reports HTTP errors as offline", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({ ok: false, status: 503 }),
    );
    const result = await fetchHealth();
    expect(result.ok).toBe(false);
    expect(result.error).toContain("503");
    vi.unstubAllGlobals();
  });

  it("reports network errors as offline", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockRejectedValue(new Error("network down")),
    );
    const result = await fetchHealth();
    expect(result.ok).toBe(false);
    expect(result.error).toContain("network down");
    vi.unstubAllGlobals();
  });
});
