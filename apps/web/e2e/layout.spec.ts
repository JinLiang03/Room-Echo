import { expect, test } from "@playwright/test";

async function assertNoHorizontalOverflow(page: import("@playwright/test").Page) {
  const metrics = await page.evaluate(() => ({
    scrollWidth: document.documentElement.scrollWidth,
    clientWidth: document.documentElement.clientWidth,
  }));
  expect(metrics.scrollWidth).toBeLessThanOrEqual(metrics.clientWidth + 1);
}

async function assertPanelsInsideViewport(
  page: import("@playwright/test").Page,
) {
  const viewport = page.viewportSize();
  const boxes = await page.locator(".panel").evaluateAll((elements) =>
    elements.map((element) => {
      const rect = element.getBoundingClientRect();
      return { left: rect.left, right: rect.right, width: rect.width };
    }),
  );
  for (const box of boxes) {
    expect(box.left).toBeGreaterThanOrEqual(-1);
    expect(box.right).toBeLessThanOrEqual((viewport?.width ?? 0) + 1);
    expect(box.width).toBeGreaterThan(0);
  }
}

test("desktop observe has no overflow and panels fit", async ({ page }) => {
  await page.goto("/#/observe");
  await expect(page.getByText(/实时信号场/)).toBeVisible();
  await assertNoHorizontalOverflow(page);
  await assertPanelsInsideViewport(page);
});

test("desktop home gives the digital life most of the first viewport", async ({
  page,
}) => {
  await page.goto("/#/home");
  await expect(page.locator(".digit-field-canvas")).toBeVisible();
  await assertNoHorizontalOverflow(page);
  const ratio = await page.locator(".digit-field-canvas").evaluate((element) => {
    const rect = element.getBoundingClientRect();
    return rect.height / window.innerHeight;
  });
  expect(ratio).toBeGreaterThanOrEqual(0.7);
  expect(ratio).toBeLessThanOrEqual(0.82);
  await expect(page.locator(".agent-voice-item")).toHaveCount(7);
  await expect(page.locator(".agent-voice-snapshot")).toHaveCount(7);
  await expect(page.locator(".agent-voice-metaphor-boundary")).toBeVisible();
  await expect(page.locator(".life-state-strip-body")).toHaveCount(7);
  await expect(page.locator(".app-footer")).toHaveText("");
  await expect(page.getByRole("radiogroup", { name: "选择数字场视觉主题" })).toHaveCount(0);
});

test("desktop story keeps everything inside the viewport", async ({ page }) => {
  await page.goto("/#/story");
  await page.getByRole("button", { name: "moving", exact: true }).click();
  await expect(page.locator(".final-card")).toBeVisible();
  await assertNoHorizontalOverflow(page);
  await assertPanelsInsideViewport(page);
});

test.describe("mobile layout", () => {
  test.use({ viewport: { width: 390, height: 844 } });

  test("story stacks signal trend lanes in a single column", async ({ page }) => {
    await page.goto("/#/story");
    await page.getByRole("button", { name: "moving", exact: true }).click();
    await assertNoHorizontalOverflow(page);
    await expect(page.locator(".trend-lane")).toHaveCount(3);
    const width = await page.locator(".trend-lane").first().evaluate((element) => {
      const rect = element.getBoundingClientRect();
      return { left: rect.left, right: rect.right, width: rect.width };
    });
    const viewport = page.viewportSize()?.width ?? 390;
    expect(width.left).toBeGreaterThanOrEqual(0);
    expect(width.right).toBeLessThanOrEqual(viewport + 1);
    expect(width.width).toBeGreaterThan(viewport * 0.8);
  });

  test("public navigation contains only now, memory, why, and settings", async ({
    page,
  }) => {
    await page.goto("/#/home");
    await expect(page.getByRole("button", { name: "此刻", exact: true })).toBeVisible();
    await expect(page.getByRole("button", { name: "记忆" })).toBeVisible();
    await expect(page.getByRole("button", { name: "为什么" })).toBeVisible();
    await expect(page.getByRole("button", { name: "设置" })).toBeVisible();
    await expect(page.getByRole("button", { name: "Story" })).toHaveCount(0);
    await expect(page.locator(".life-state-strip-body")).toHaveCount(7);
    await expect(page.locator(".agent-voice-item")).toHaveCount(7);
    await expect(page.locator(".agent-voice-metaphor-boundary")).toBeVisible();
    await expect(page.locator(".app-footer")).toHaveText("");
    await assertNoHorizontalOverflow(page);
  });

  test("home keeps no-data moments incomplete and non-saveable", async ({ page }) => {
    await page.routeWebSocket("**/ws", async (socket) => {
      await socket.close();
    });
    await page.goto("/#/home");
    await expect(page.locator(".digit-field-canvas")).toBeVisible();
    await assertNoHorizontalOverflow(page);
    await expect(page.locator(".digit-field")).toHaveAttribute("data-life-active", "false");
    await expect(page.getByRole("button", { name: /保存这一刻/ })).toHaveCount(0);
    await page.getByRole("button", { name: "记忆" }).click();
    await expect(page.locator(".memory-glyph")).toHaveCount(0);
  });
});

test("keyboard navigation reaches why and settings", async ({ page }) => {
  await page.goto("/#/home");
  const why = page.getByRole("button", { name: "为什么" });
  for (let index = 0; index < 8; index += 1) {
    if (await why.evaluate((element) => element === document.activeElement)) {
      break;
    }
    await page.keyboard.press("Tab");
  }
  await expect(why).toBeFocused();
  await page.keyboard.press("Enter");
  await expect(page.locator(".why-summary")).toBeVisible();
  await expect(page.getByRole("button", { name: "设置" })).toBeVisible();
});

test("reduced motion keeps live Agent text readable without entry animation", async ({
  page,
}) => {
  await page.emulateMedia({ reducedMotion: "reduce" });
  await page.goto("/#/home");
  await expect(page.locator(".agent-voice-content").first()).toBeVisible();
  const animationName = await page
    .locator(".agent-voice-content")
    .first()
    .evaluate((element) => getComputedStyle(element).animationName);
  expect(animationName).toBe("none");
});
