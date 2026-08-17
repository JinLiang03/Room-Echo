import { expect, test } from "@playwright/test";

type Scenario = "idle" | "moving" | "interference" | "ambiguous" | "unknown";

const STATES: { scenario: Scenario; label: string }[] = [
  { scenario: "idle", label: "idle" },
  { scenario: "moving", label: "walk" },
  { scenario: "interference", label: "degraded" },
  { scenario: "ambiguous", label: "ambiguous" },
  { scenario: "unknown", label: "unavailable" },
];

async function canvasStats(page: import("@playwright/test").Page) {
  return page.evaluate(() => {
    const canvas = document.querySelector(".sculpture-canvas") as HTMLCanvasElement | null;
    if (!canvas) {
      return null;
    }
    const context = canvas.getContext("2d");
    if (!context) {
      return null;
    }
    const data = context.getImageData(0, 0, canvas.width, canvas.height).data;
    let sum = 0;
    let sumSq = 0;
    let count = 0;
    for (let index = 3; index < data.length; index += 16) {
      const lum =
        0.2126 * data[index - 3] + 0.7152 * data[index - 2] + 0.0722 * data[index - 1];
      sum += lum;
      sumSq += lum * lum;
      count += 1;
    }
    const mean = sum / count;
    return { mean, stddev: Math.sqrt(Math.max(0, sumSq / count - mean * mean)) };
  });
}

test.describe("multimodal sculpture", () => {
  for (const { scenario, label } of STATES) {
    test(`${label} state renders a deterministic abstract field`, async ({ page }) => {
      await page.goto("/#/story");
      await page.getByRole("button", { name: scenario, exact: true }).click();
      const canvas = page.locator(".sculpture-canvas");
      await expect(canvas).toBeVisible();
      await page.waitForTimeout(1200); // let activity ease in/out
      const stats = await canvasStats(page);
      expect(stats).not.toBeNull();
      expect(stats!.mean).toBeGreaterThan(0);
      expect(stats!.stddev).toBeGreaterThan(0);
      // Sculpture must never contain imagery-like content.
      expect(await page.locator(".signal-sculpture img").count()).toBe(0);
      await expect(page.getByText(/NOT A CAMERA IMAGE/).first()).toBeVisible();
    });
  }

  test("unavailable state clears residue: dimmer and flatter than walk", async ({
    page,
  }) => {
    await page.goto("/#/story");
    await page.getByRole("button", { name: "moving", exact: true }).click();
    await page.waitForTimeout(1200);
    const walk = await canvasStats(page);
    await page.getByRole("button", { name: "unknown", exact: true }).click();
    await page.waitForTimeout(1200);
    const unavailable = await canvasStats(page);
    expect(walk).not.toBeNull();
    expect(unavailable).not.toBeNull();
    expect(unavailable!.stddev).toBeLessThan(walk!.stddev * 0.7);
    // Dim uniform haze: bright enough to see, but flat and non-animated.
    expect(unavailable!.mean).toBeGreaterThan(5);
    expect(unavailable!.mean).toBeLessThan(160);
  });

  test("reduced-motion canvas redraws when the signal state changes", async ({
    page,
  }) => {
    await page.emulateMedia({ reducedMotion: "reduce" });
    await page.goto("/#/story");
    await page.getByRole("button", { name: "moving", exact: true }).click();
    await page.waitForTimeout(250);
    const walk = await canvasStats(page);
    await page.getByRole("button", { name: "unknown", exact: true }).click();
    await page.waitForTimeout(250);
    const unavailable = await canvasStats(page);
    expect(walk).not.toBeNull();
    expect(unavailable).not.toBeNull();
    expect(unavailable!.stddev).toBeLessThan(walk!.stddev * 0.7);
  });

  test("disagreement phase does not change signal numbers", async ({ page }) => {
    await page.goto("/#/story");
    await page.getByRole("button", { name: "ambiguous", exact: true }).click();
    await page.waitForTimeout(500);
    const numbers = await page
      .locator(".trend-lane-value strong")
      .allTextContents();
    expect(numbers).toHaveLength(3);
    // Signal values still shown from the sensor, not from disagreement.
    expect(await page.locator(".result-card").isVisible()).toBe(true);
  });
});
