import { spawn } from "node:child_process";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { chromium } from "playwright";

const webDir = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const artifactDir = path.resolve(webDir, "../../artifacts/web");
const port = 5200;
const base = `http://127.0.0.1:${port}`;
const server = spawn(
  "npm",
  ["run", "dev", "--", "--host", "127.0.0.1", "--port", String(port)],
  { cwd: webDir, stdio: "ignore" },
);

let browser;
try {
  await waitForServer();
  browser = await chromium.launch({ channel: "chrome" });
  const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
  await page.goto(`${base}/#/settings`);
  await page.getByLabel("调试信息(sequence/丢弃/连接)").check();
  await page.getByRole("button", { name: "此刻", exact: true }).click();
  const canvas = page.locator(".digit-field-canvas");
  await canvas.waitFor({ state: "visible" });
  await canvas.scrollIntoViewIfNeeded();
  const box = await canvas.boundingBox();
  if (!box) {
    throw new Error("digit field canvas has no bounding box");
  }
  for (let step = 0; step < 20; step += 1) {
    const phase = (step / 20) * Math.PI * 2;
    await page.mouse.move(
      box.x + box.width * (0.5 + Math.cos(phase) * 0.22),
      box.y + box.height * (0.5 + Math.sin(phase) * 0.22),
    );
    await page.waitForTimeout(500);
  }

  const values = await page.locator(".digit-field-debug span").allTextContents();
  const metrics = Object.fromEntries(
    values.map((value) => {
      const [key, raw] = value.trim().split(/\s+/, 2);
      return [key, Number(raw)];
    }),
  );
  const pass =
    Number.isFinite(metrics.fps) &&
    metrics.fps >= 45 &&
    metrics.dropped <= 12 &&
    metrics.draws <= 1_100;
  const report = {
    mapping_version: "digit-field-v1",
    duration_s: 10,
    point_count: 900,
    fps: metrics.fps,
    draw_calls: metrics.draws,
    dropped_visual_frames: metrics.dropped,
    pointer_deformation: true,
    morph_theme: "signal-driven-life-cycle",
    pass,
    recorded_at: new Date().toISOString(),
  };
  fs.mkdirSync(artifactDir, { recursive: true });
  fs.writeFileSync(
    path.join(artifactDir, "digit-field-perf.json"),
    `${JSON.stringify(report, null, 2)}\n`,
  );
  console.log(JSON.stringify(report, null, 2));
  if (!pass) {
    process.exitCode = 1;
  }
} finally {
  await browser?.close();
  server.kill();
}

async function waitForServer(timeoutMs = 30_000) {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    try {
      const response = await fetch(base);
      if (response.ok) {
        return;
      }
    } catch {
      // The dev server is still starting.
    }
    await new Promise((resolve) => setTimeout(resolve, 250));
  }
  throw new Error("vite dev server did not start");
}
