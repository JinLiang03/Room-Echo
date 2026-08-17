import { expect, test } from "@playwright/test";
import path from "node:path";

const ARTIFACT_DIR = path.resolve(process.cwd(), "../../artifacts/web");

function shotPath(base: string): string {
  const project = test.info().project.name;
  return path.join(ARTIFACT_DIR, `${project}-${base}.png`);
}

test.describe("visual artifacts", () => {
  const fiveStates: { scenario: string; file: string }[] = [
    { scenario: "idle", file: "state-idle" },
    { scenario: "moving", file: "state-walk" },
    { scenario: "interference", file: "state-degraded" },
    { scenario: "ambiguous", file: "state-ambiguous" },
    { scenario: "unknown", file: "state-unavailable" },
  ];

  test("captures observe and story screenshots at desktop size", async ({
    page,
  }) => {
    test.skip(test.info().project.name !== "desktop", "desktop artifact only");
    await page.goto("/#/home");
    await expect(page.locator(".digit-field-canvas")).toBeVisible();
    await page.evaluate(() => window.scrollTo(0, 0));
    await page.waitForTimeout(900);
    await page.screenshot({
      path: shotPath("home-digit-field"),
    });

    await page.goto("/#/observe");
    await expect(page.getByText(/实时信号场/)).toBeVisible();
    await page.screenshot({
      path: shotPath("observe"),
      fullPage: true,
    });

    await page.goto("/#/story");
    await page.getByRole("button", { name: "moving", exact: true }).click();
    await expect(page.locator(".final-card")).toBeVisible();
    await page.screenshot({
      path: shotPath("story-moving"),
      fullPage: true,
    });

    await page.getByRole("button", { name: "rejected", exact: true }).click();
    await expect(page.getByText(/forbidden_wall_presence/)).toBeVisible();
    await page.screenshot({
      path: shotPath("council-rejected"),
      fullPage: true,
    });

    await expect(page.locator(".evidence-view")).toBeVisible();
    await page.screenshot({
      path: shotPath("evidence"),
      fullPage: true,
    });

    for (const state of fiveStates) {
      await page.getByRole("button", { name: state.scenario, exact: true }).click();
      await page.waitForTimeout(1200);
      await page.screenshot({
        path: shotPath(state.file),
        fullPage: true,
      });
    }
  });

  test("captures story screenshot at mobile size", async ({ page }) => {
    test.skip(test.info().project.name !== "mobile", "mobile artifact only");
    await page.goto("/#/home");
    await expect(page.locator(".digit-field-canvas")).toBeVisible();
    await page.evaluate(() => window.scrollTo(0, 0));
    await page.waitForTimeout(900);
    await page.screenshot({
      path: shotPath("home-digit-field"),
    });

    await page.goto("/#/story");
    await page.getByRole("button", { name: "moving", exact: true }).click();
    await expect(page.locator(".final-card")).toBeVisible();
    await page.screenshot({
      path: shotPath("story-moving"),
      fullPage: true,
    });

    await page.getByRole("button", { name: "single_rx", exact: true }).click();
    await expect(page.locator(".trend-lane")).toHaveCount(3);
    await expect(page.locator(".trend-band-health")).toContainText(/unknown|不可用|不足|insufficient_signal/);
    await page.screenshot({
      path: shotPath("story-single-rx"),
      fullPage: true,
    });

    for (const state of ["idle", "interference", "ambiguous", "unknown"]) {
      await page.getByRole("button", { name: state, exact: true }).click();
      await page.waitForTimeout(1200);
      await page.screenshot({
        path: shotPath(state),
        fullPage: true,
      });
    }
  });
});
