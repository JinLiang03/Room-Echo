import { expect, test } from "@playwright/test";

test("observe view renders shell, watermark, and offline honesty", async ({
  page,
}) => {
  // Keep this case isolated from any replay API a developer may already have
  // running on port 8000. The routed socket closes immediately, reproducing
  // the no-backend condition this test is meant to cover.
  await page.routeWebSocket("**/ws", async (socket) => {
    await socket.close();
  });
  await page.goto("/#/observe");
  await expect(page.getByText(/NOT A CAMERA IMAGE/).first()).toBeVisible();
  await expect(page.getByText(/实时信号场/)).toBeVisible();
  await expect(page.getByRole("button", { name: "此刻", exact: true })).toHaveAttribute("aria-current", "page");
  // Without a backend, the app must show the stale/offline state rather than
  // pretending data is live.
  await expect(page.getByText(/连接已断开/).or(page.getByText(/回放已暂停/))).toBeVisible();
});

test("story route cycles all visual states and keeps watermark", async ({
  page,
}) => {
  await page.goto("/#/story");
  await expect(page.getByRole("group", { name: "选择场景" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Story" })).toHaveCount(0);
  await expect(page.getByText(/连接已断开/)).toHaveCount(0);
  await expect(page.getByRole("button", { name: "Start" })).toHaveCount(0);
  const scenarios = [
    "idle",
    "moving",
    "interference",
    "single_rx",
    "unknown",
    "ambiguous",
    "timeout",
    "rejected",
  ];
  for (const scenario of scenarios) {
    await page.getByRole("button", { name: scenario, exact: true }).click();
    await expect(page.getByText(/固定状态演示/)).toBeVisible();
  }
  await expect(page.getByText(/NOT A CAMERA IMAGE/).first()).toBeVisible();
});

test("council story renders claims, rejections, and final result", async ({
  page,
}) => {
  await page.goto("/#/story");
  await page.getByRole("button", { name: "rejected", exact: true }).click();
  await expect(page.getByText(/forbidden_wall_presence/)).toBeVisible();
  await expect(page.locator(".final-card")).toBeVisible();
});
