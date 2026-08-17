import { spawnSync } from "node:child_process";
import { mkdtemp, mkdir, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { chromium } from "@playwright/test";

const scriptDir = path.dirname(fileURLToPath(import.meta.url));
const webDir = path.resolve(scriptDir, "..");
const artifactDir = path.resolve(webDir, "../../artifacts/design");
const outputPath = path.join(artifactDir, "digit-field-morph.gif");
const frameDir = await mkdtemp(path.join(tmpdir(), "wsc-digit-field-"));
const url = process.env.DIGIT_FIELD_URL ?? "http://127.0.0.1:5173/#/home";
const ffmpeg = process.env.FFMPEG_BIN ?? "ffmpeg";

let browser;
try {
  await mkdir(artifactDir, { recursive: true });
  browser = await chromium.launch({ headless: true, channel: "chrome" });
  const page = await browser.newPage({
    viewport: { width: 1040, height: 700 },
    deviceScaleFactor: 1,
    reducedMotion: "no-preference",
  });
  await page.goto(url, { waitUntil: "domcontentloaded" });
  await page.addStyleTag({
    content: ".topbar,.stale-overlay,.alert-tray{display:none!important}",
  });
  const stage = page.locator(".home-field-stage");
  await stage.waitFor({ state: "visible" });
  await page
    .locator('.digit-field[data-life-active="true"]')
    .waitFor({ state: "attached", timeout: 15_000 });

  let frame = 0;
  for (let step = 0; step < 65; step += 1) {
    await stage.screenshot({
      path: path.join(frameDir, `frame-${String(frame).padStart(3, "0")}.png`),
      animations: "allow",
    });
    frame += 1;
    await page.waitForTimeout(100);
  }

  const palettePath = path.join(frameDir, "palette.png");
  run(ffmpeg, [
    "-y",
    "-framerate",
    "10",
    "-i",
    path.join(frameDir, "frame-%03d.png"),
    "-vf",
    "fps=10,scale=960:-2:flags=lanczos,palettegen=stats_mode=diff",
    palettePath,
  ]);
  run(ffmpeg, [
    "-y",
    "-framerate",
    "10",
    "-i",
    path.join(frameDir, "frame-%03d.png"),
    "-i",
    palettePath,
    "-lavfi",
    "fps=10,scale=960:-2:flags=lanczos[x];[x][1:v]paletteuse=dither=bayer:bayer_scale=3:diff_mode=rectangle",
    "-loop",
    "0",
    outputPath,
  ]);
  console.log(`Wrote ${frame} frames to ${outputPath}`);
} finally {
  await browser?.close();
  await rm(frameDir, { recursive: true, force: true });
}

function run(command, args) {
  const result = spawnSync(command, args, { stdio: "inherit" });
  if (result.error) {
    throw result.error;
  }
  if (result.status !== 0) {
    throw new Error(`${command} exited with status ${result.status}`);
  }
}
