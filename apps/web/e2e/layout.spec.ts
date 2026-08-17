import { expect, test } from "@playwright/test";
import { simulatedCareScenarios } from "../src/generated/fixtures";

test.beforeEach(async ({ page }) => {
  await page.route("**/api/care/scenario*", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(simulatedCareScenarios[0]),
    });
  });
});

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

async function assertTwoByTwoSuggestions(
  page: import("@playwright/test").Page,
) {
  const cards = await page.locator(".action-suggestion").evaluateAll((elements) =>
    elements.map((element) => {
      const rect = element.getBoundingClientRect();
      return { top: rect.top, left: rect.left, width: rect.width };
    }),
  );
  expect(cards).toHaveLength(4);
  expect(Math.abs(cards[0].top - cards[1].top)).toBeLessThanOrEqual(1);
  expect(Math.abs(cards[2].top - cards[3].top)).toBeLessThanOrEqual(1);
  expect(cards[2].top).toBeGreaterThan(cards[0].top + 20);
  expect(cards[1].left).toBeGreaterThan(cards[0].left + cards[0].width - 1);
}

test("desktop observe has no overflow and panels fit", async ({ page }) => {
  await page.goto("/#/observe");
  await expect(page.getByText(/实时信号场/)).toBeVisible();
  await assertNoHorizontalOverflow(page);
  await assertPanelsInsideViewport(page);
});

test("desktop home presents one Agent beside the current digit field", async ({
  page,
}) => {
  await page.goto("/#/home?care=bathroom_timeout");
  await expect(page.locator(".digit-field-canvas")).toBeVisible();
  await assertNoHorizontalOverflow(page);
  const fieldMetrics = await page.locator(".digit-field-canvas").evaluate((element) => {
    const rect = element.getBoundingClientRect();
    return {
      ratio: rect.height / window.innerHeight,
      mobile: window.innerWidth <= 760,
    };
  });
  if (fieldMetrics.mobile) {
    expect(fieldMetrics.ratio).toBeGreaterThanOrEqual(0.66);
    expect(fieldMetrics.ratio).toBeLessThanOrEqual(0.72);
  } else {
    expect(fieldMetrics.ratio).toBeGreaterThanOrEqual(0.98);
    expect(fieldMetrics.ratio).toBeLessThanOrEqual(1.02);
  }
  await expect(page.locator('[data-public-agent="room-echo"]')).toHaveCount(1);
  await expect(page.locator(".agent-action-window")).toHaveCount(1);
  await expect(page.locator(".action-suggestion")).toHaveCount(4);
  await expect(page.locator('[data-action-source="care_workflow"]')).toHaveCount(4);
  await expect(page.getByText("SIM · CARE")).toBeVisible();
  await expect(page.locator(".care-scenario-selector")).toHaveCount(0);
  await expect(page.locator(".room-echo-context")).toHaveCount(0);
  await expect(page.locator(".room-agent-status li")).toHaveCount(2);
  await expect(page.locator(".room-agent-confidence")).toHaveCount(0);
  await expect(page.locator(".action-suggestion footer")).toHaveCount(0);
  await assertTwoByTwoSuggestions(page);
  await expect(page.locator(".digit-field")).toHaveAttribute("data-show-perimeter", "false");
  await expect(page.locator(".agent-voice-item")).toHaveCount(0);
  await expect(page.locator(".life-state-strip-body")).toHaveCount(0);
  await expect(page.locator(".app-footer")).toHaveCount(0);
  await expect(page.getByRole("radiogroup", { name: "选择数字场视觉主题" })).toHaveCount(0);

});

test("default home activates the single-page accelerated care day", async ({ page }) => {
  await page.goto("/#/home");
  await expect(page.locator('[data-care-simulation="true"]')).toHaveCount(1);
  await expect(page.locator('[data-action-source="care_workflow"]')).toHaveCount(4);
  await expect(page.getByText("SIM · CARE")).toBeVisible();
  await expect(page.locator('[data-public-agent="room-echo"]')).toHaveAttribute(
    "data-care-moment",
    "routine",
  );
  const bindings = await page.locator(
    '[data-public-agent="room-echo"], .agent-action-window, .digit-field',
  ).evaluateAll((elements) =>
    elements.map((element) => ({
      evidence: element.getAttribute("data-evidence-hash"),
      session: element.getAttribute("data-session-id"),
      window: element.getAttribute("data-window-id"),
    })),
  );
  expect(bindings).toHaveLength(3);
  expect(new Set(bindings.map((item) => item.evidence)).size).toBe(1);
  expect(new Set(bindings.map((item) => item.session)).size).toBe(1);
  expect(new Set(bindings.map((item) => item.window)).size).toBe(1);

  const initialEvidence = bindings[0].evidence;
  const initialWindow = bindings[0].window;
  await expect(page.locator('[data-public-agent="room-echo"]')).toHaveAttribute(
    "data-care-moment",
    "bathroom_timeout",
    { timeout: 10_000 },
  );
  await expect(page.getByText("卫生间停留超过模拟关注阈值")).toBeVisible();
  expect(page.url()).toContain("#/home");
  expect(page.url()).not.toContain("care=");

  const nextBindings = await page.locator(
    '[data-public-agent="room-echo"], .agent-action-window, .digit-field',
  ).evaluateAll((elements) =>
    elements.map((element) => ({
      evidence: element.getAttribute("data-evidence-hash"),
      session: element.getAttribute("data-session-id"),
      window: element.getAttribute("data-window-id"),
    })),
  );
  expect(new Set(nextBindings.map((item) => item.evidence)).size).toBe(1);
  expect(new Set(nextBindings.map((item) => item.session)).size).toBe(1);
  expect(new Set(nextBindings.map((item) => item.window)).size).toBe(1);
  expect(nextBindings[0].evidence).not.toBe(initialEvidence);
  expect(nextBindings[0].window).not.toBe(initialWindow);
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

  test("home navigation contains only now, memory, and why", async ({
    page,
  }) => {
    await page.goto("/#/home");
    await expect(page.getByRole("button", { name: "此刻", exact: true })).toBeVisible();
    await expect(page.getByRole("button", { name: "记忆" })).toBeVisible();
    await expect(page.getByRole("button", { name: "为什么" })).toBeVisible();
    await expect(page.getByRole("button", { name: "设置" })).toHaveCount(0);
    await expect(page.getByRole("button", { name: "Story" })).toHaveCount(0);
    await expect(page.locator('[data-public-agent="room-echo"]')).toHaveCount(1);
    await expect(page.locator(".agent-action-window")).toHaveCount(1);
    await expect(page.locator(".action-suggestion")).toHaveCount(4);
    await expect(page.locator(".care-scenario-selector")).toHaveCount(0);
    await expect(page.locator(".room-echo-context")).toHaveCount(0);
    await assertTwoByTwoSuggestions(page);
    await expect(page.locator(".life-state-strip-body")).toHaveCount(0);
    await expect(page.locator(".agent-voice-item")).toHaveCount(0);
    await expect(page.locator(".app-footer")).toHaveCount(0);
    await assertNoHorizontalOverflow(page);
  });

  test("home keeps no-data moments incomplete and non-saveable", async ({ page }) => {
    await page.unroute("**/api/care/scenario*");
    await page.route("**/api/care/scenario*", async (route) => {
      await route.fulfill({
        status: 503,
        contentType: "application/json",
        body: JSON.stringify({ detail: "scenario unavailable" }),
      });
    });
    await page.routeWebSocket("**/ws", async (socket) => {
      await socket.close();
    });
    await page.goto("/#/home");
    await expect(page.locator(".digit-field-canvas")).toBeVisible();
    await assertNoHorizontalOverflow(page);
    await expect(page.locator(".digit-field")).toHaveAttribute("data-life-active", "false");
    await expect(page.getByText("SIM · CARE · UNAVAILABLE")).toBeVisible();
    await expect(page.locator('[data-action-source="care_workflow"]')).toHaveCount(4);
    await expect(page.locator('[data-action-status="withheld"]')).toHaveCount(4);
    for (const selector of [
      '[data-public-agent="room-echo"]',
      ".agent-action-window",
      ".digit-field",
    ]) {
      await expect(page.locator(selector)).toHaveAttribute("data-evidence-hash", "waiting");
      await expect(page.locator(selector)).toHaveAttribute("data-session-id", "waiting");
      await expect(page.locator(selector)).toHaveAttribute("data-window-id", "waiting");
    }
    await expect(page.getByRole("button", { name: /保存这一刻/ })).toHaveCount(0);
    await page.getByRole("button", { name: "记忆" }).click();
    await expect(page.locator(".memory-glyph")).toHaveCount(0);
  });
});

test("memory and why share the glass Room Echo public shell", async ({ page }) => {
  await page.goto("/#/replay");
  await expect(page.getByText("本机视觉书签 · 非场景识别")).toBeVisible();
  await expect(page.locator(".memory-toolbar")).toBeVisible();
  await expect(page.locator(".room-echo-page-lead")).toHaveCount(0);
  await expect(page.locator(".care-day-memory")).toHaveCount(0);
  await expect(page.locator(".care-scenario-selector")).toHaveCount(0);
  await expect(page.locator(".app-footer")).toHaveCount(1);
  await assertNoHorizontalOverflow(page);

  await page.getByRole("button", { name: "为什么" }).click();
  await expect(page.locator(".why-summary")).toBeVisible();
  await expect(page.locator(".room-echo-page-lead")).toHaveCount(0);
  await expect(page.locator('[data-public-agent="room-echo"]')).toHaveCount(0);
  await expect(page.locator(".why-care-evidence")).toHaveCount(0);
  await expect(page.locator(".care-scenario-selector")).toHaveCount(0);
  await expect(page.locator(".council-view")).toHaveCount(0);
  await expect(page.locator(".app-footer")).toHaveCount(1);
  await assertNoHorizontalOverflow(page);
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

test("reduced motion keeps the single Agent readable without presence animation", async ({
  page,
}) => {
  await page.emulateMedia({ reducedMotion: "reduce" });
  await page.goto("/#/home");
  await expect(page.locator(".room-agent-status")).toBeVisible();
  await expect(page.locator(".room-agent-status li")).toHaveCount(2);
});
