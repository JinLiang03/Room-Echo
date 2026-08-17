import { defineConfig } from "@playwright/test";

const apiPort = process.env.E2E_API_PORT ?? "18000";
const webPort = process.env.E2E_WEB_PORT ?? "15173";
const apiOrigin = `http://127.0.0.1:${apiPort}`;
const webOrigin = `http://127.0.0.1:${webPort}`;

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
    baseURL: webOrigin,
    trace: "retain-on-failure",
  },
  webServer: [
    {
      command:
        `cd ../../ && APP_MODE=replay DEMO_AUTOSTART=1 SCENARIO=demo_2min AGENT_PROVIDER=mock uv run uvicorn wifi_api.app:app --host 127.0.0.1 --port ${apiPort}`,
      url: `${apiOrigin}/healthz`,
      reuseExistingServer: false,
      timeout: 60_000,
      env: {
        APP_MODE: "replay",
        DEMO_AUTOSTART: "1",
        SCENARIO: "demo_2min",
        AGENT_PROVIDER: "mock",
      },
    },
    {
      command: `WSC_API_ORIGIN=${apiOrigin} WSC_WEB_PORT=${webPort} npm run dev -- --host 127.0.0.1 --port ${webPort} --strictPort`,
      url: webOrigin,
      reuseExistingServer: false,
      timeout: 60_000,
    },
  ],
  projects: [
    { name: "desktop", use: { viewport: { width: 1440, height: 900 }, channel: "chrome" } },
    { name: "mobile", use: { viewport: { width: 390, height: 844 }, channel: "chrome" } },
  ],
});
