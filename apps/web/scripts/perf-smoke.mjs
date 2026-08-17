/* Multimodal perf smoke: runs the #/perf harness and records FPS/draws/events/audio nodes. */
import { spawn } from "node:child_process";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { chromium } from "playwright";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const artifactDir = path.resolve(root, "../../artifacts/web");
const port = 5199;
const base = `http://127.0.0.1:${port}`;

const server = spawn(
  "npm",
  ["run", "dev", "--", "--host", "127.0.0.1", "--port", String(port)],
  { cwd: root, stdio: "ignore" },
);

async function waitForServer(timeoutMs = 30000) {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    try {
      const response = await fetch(base);
      if (response.ok) {
        return;
      }
    } catch {
      // not up yet
    }
    await new Promise((resolve) => setTimeout(resolve, 250));
  }
  throw new Error("vite dev server did not start");
}

async function main() {
  await waitForServer();
  const browser = await chromium.launch({ channel: "chrome" });
  try {
    const page = await browser.newPage({ viewport: { width: 1280, height: 800 } });
    await page.goto(`${base}/#/perf?seconds=10&rate=30`);
    await page.waitForFunction(() => window.__wscPerf?.done === true, {
      timeout: 30000,
    });
    const first = await page.evaluate(() => window.__wscPerf);
    await page.waitForTimeout(2000);
    const second = await page.evaluate(() => window.__wscPerf);

    const expectedEvents = 10 * 30;
    const pass =
      first.fps >= 45 &&
      first.dropped <= 12 &&
      first.eventsInjected >= expectedEvents * 0.9 &&
      first.nodeCount <= 16 &&
      second.nodeCount === first.nodeCount;
    const report = {
      mapping_version: "multimodal-v1",
      duration_s: 10,
      rate_hz: 30,
      fps: first.fps,
      draw_calls: first.drawCalls,
      dropped_visual_frames: first.dropped,
      events_injected: first.eventsInjected,
      audio_node_count: first.nodeCount,
      audio_node_count_after: second.nodeCount,
      pass,
      fallback:
        first.fps < 60
          ? `headless FPS ${first.fps} below 60; recorded as explicit fallback`
          : null,
      recorded_at: new Date().toISOString(),
    };
    fs.mkdirSync(artifactDir, { recursive: true });
    fs.writeFileSync(
      path.join(artifactDir, "perf-smoke.json"),
      JSON.stringify(report, null, 2) + "\n",
    );
    console.log(JSON.stringify(report, null, 2));
    if (!pass) {
      process.exitCode = 1;
    }
  } finally {
    await browser.close();
    server.kill();
  }
}

main().catch((error) => {
  console.error(error);
  server.kill();
  process.exitCode = 1;
});
