import { expect, test } from "@playwright/test";
import path from "node:path";

const ARTIFACT_DIR = path.resolve(process.cwd(), "../../artifacts/web");

test("home consumes the replay triplet as one signal-driven digital life", async ({
  page,
}) => {
  await page.goto("/#/home");
  await expect(page.locator(".digit-field-canvas")).toBeVisible();
  await expect(page.locator(".digit-field")).not.toHaveAttribute("data-life-state", "doubt", {
    timeout: 30_000,
  });
  await expect(page.locator(".digit-field")).toHaveAttribute("data-life-active", "true");
  await expect(page.locator(".agent-voice-item")).toHaveCount(0);
  await page.waitForTimeout(4_200);
  await page.screenshot({
    path: path.join(
      ARTIFACT_DIR,
      `${test.info().project.name}-home-digit-field-live.png`,
    ),
  });
  const before = await page.locator(".digit-field").getAttribute("data-life-state");
  await page.mouse.move(600, 430);
  const after = await page.locator(".digit-field").getAttribute("data-life-state");
  expect(after).toBe(before);

  await page.getByRole("button", { name: /点击或长按保存这一刻/ }).click();
  await page.getByRole("button", { name: "记忆" }).click();
  await expect(page.locator(".memory-glyph")).toHaveCount(1);
  await expect(page.getByText("本机视觉书签 · 非场景识别")).toBeVisible();
  await expect(page.getByText("评委模式 · 技术回放")).toHaveCount(0);

  // The result card is the canonical place where the sensor cap and final
  // claim confidence are shown together; keep the safety invariant covered.
  await page.goto("/#/observe");
  await expect(page.locator(".result-card")).toBeVisible();
  const confidenceValues = page.locator(".confidence-separation dd");
  await expect(confidenceValues.nth(2)).not.toHaveText("—", { timeout: 30_000 });
  const resultCap = Number.parseFloat(await confidenceValues.nth(0).innerText());
  const finalClaim = Number.parseFloat(await confidenceValues.nth(2).innerText());
  expect(finalClaim).toBeLessThanOrEqual(resultCap * 100 + 0.001);
});

test("happy replay: signals flow and council debate reaches the UI", async ({
  page,
}) => {
  await page.goto("/#/observe");
  // Watermark and sculpture render.
  await expect(page.getByText(/NOT A CAMERA IMAGE/).first()).toBeVisible();
  await expect(page.locator(".sculpture-canvas")).toBeVisible();

  // Live signal frames arrive from the replay stream.
  await expect(page.locator(".scene-meta-strip")).toContainText(/window/, {
    timeout: 30_000,
  });

  // Council result with claims reaches the result card.
  await expect(page.locator(".result-card")).toContainText(/supported|ambiguous|unavailable|讨论不可用/, {
    timeout: 60_000,
  });
  await expect(page.locator(".result-headline")).toBeVisible();

  // Council view shows evidence chips and at least one cycle.
  await page.getByRole("button", { name: "为什么" }).click();
  await page.getByText("Agent 审议", { exact: true }).click();
  await expect(page.locator(".cycle-card").first()).toBeVisible({ timeout: 60_000 });
  // 来源/证据默认折叠,展开后应能看到证据 chips 与逐步推理轨迹.
  await page.locator(".claim-details summary").first().click();
  await expect(page.locator(".analysis-trace").first()).toBeVisible({
    timeout: 30_000,
  });
  await expect(page.locator(".systematic-reading").first()).toBeVisible({
    timeout: 30_000,
  });
  await expect(page.locator(".reading-layers li").first()).toBeVisible();
  await expect(page.locator(".evidence-chip").first()).toBeVisible({
    timeout: 30_000,
  });

  // Replay controls respond (pause then resume).
  await page.getByRole("button", { name: "记忆" }).click();
  await expect(page.getByText("评委模式 · 技术回放")).toHaveCount(0);
  await page.goto("/#/replay?audit=1");
  await page.getByRole("button", { name: "暂停" }).click();
  await page.getByRole("button", { name: "播放" }).click();
});

test("agent discussion renders without blocking signals", async ({ page }) => {
  await page.goto("/#/observe");
  await expect(page.locator(".trend-lane").first()).toBeVisible();
  await expect(page.locator(".trend-lane-value strong").first()).toBeVisible({
    timeout: 30_000,
  });
});

test("refresh and late join restore source, signal history, challenge, and final", async ({
  page,
}) => {
  await page.goto("/#/council");
  await page.getByText("Agent 审议", { exact: true }).click();
  await expect(page.locator(".claim-details").first()).toBeVisible({
    timeout: 90_000,
  });
  await expect(page.locator(".challenge-row").first()).toBeVisible({
    timeout: 90_000,
  });
  await expect(page.locator(".final-card").first()).toBeVisible({
    timeout: 90_000,
  });

  await page.reload();
  await page.getByText("Agent 审议", { exact: true }).click();
  await expect(page.locator(".claim-details").first()).toBeVisible({
    timeout: 30_000,
  });
  await expect(page.locator(".challenge-row").first()).toBeVisible();
  await expect(page.locator(".final-card").first()).toBeVisible();

  await page.goto("/#/observe");
  await expect(page.locator(".scene-meta-strip")).toContainText(/window\s+(?!—)\S+/, {
    timeout: 30_000,
  });
  const sparklinePoints =
    (await page.locator(".trend-lane polyline").first().getAttribute("points")) ?? "";
  expect(sparklinePoints).not.toContain("NaN");
});

test("backward seek and paused step have stable transport semantics", async ({ page }) => {
  await page.goto("/#/replay?audit=1");
  const frames = page
    .locator(".transport-stats > div")
    .filter({ has: page.getByText("frames", { exact: true }) })
    .locator("dd");
  const position = page
    .locator(".transport-stats > div")
    .filter({ has: page.getByText("position", { exact: true }) })
    .locator("dd");

  await expect(frames).not.toHaveText("0", { timeout: 30_000 });
  const pause = page.getByRole("button", { name: "暂停", exact: true });
  if (await pause.isVisible()) {
    await pause.click();
  }
  await expect(page.getByRole("button", { name: "播放", exact: true })).toBeVisible();

  await page.getByRole("button", { name: "回到起点", exact: true }).click();
  await expect(position).toHaveText("0.0s", { timeout: 10_000 });
  await expect(frames).toHaveText("0", { timeout: 10_000 });

  await page.getByRole("button", { name: "单步 +10", exact: true }).click();
  await expect(frames).toHaveText("10", { timeout: 10_000 });
  await expect(page.getByRole("button", { name: "播放", exact: true })).toBeVisible();

  await page.getByRole("button", { name: "播放", exact: true }).click();
});
