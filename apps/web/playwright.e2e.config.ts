import { defineConfig } from "@playwright/test";

/**
 * Full-stack E2E: real API (replay demo autostart) + Vite web app.
 * Used by `make e2e-replay`.
 */
export default defineConfig({
  testDir: "./e2e/live",
  timeout: 120_000,
  workers: 1,
  retries: 0,
  reporter: [["list"]],
  use: {
    baseURL: "http://127.0.0.1:5173",
    trace: "retain-on-failure",
  },
  webServer: [
    {
      command:
        "cd ../../ && APP_MODE=replay DEMO_AUTOSTART=1 SCENARIO=demo_2min uv run uvicorn wifi_api.app:app --host 127.0.0.1 --port 8000",
      url: "http://127.0.0.1:8000/healthz",
      reuseExistingServer: true,
      timeout: 60_000,
      env: { APP_MODE: "replay", DEMO_AUTOSTART: "1", SCENARIO: "demo_2min" },
    },
    {
      command: "npm run dev -- --host 127.0.0.1",
      url: "http://127.0.0.1:5173",
      reuseExistingServer: true,
      timeout: 60_000,
    },
  ],
  projects: [
    { name: "desktop", use: { viewport: { width: 1440, height: 900 }, channel: "chrome" } },
    { name: "mobile", use: { viewport: { width: 390, height: 844 }, channel: "chrome" } },
  ],
});
