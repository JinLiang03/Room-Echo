import { describe, expect, it } from "vitest";
import { createDigitRingPoints, digitPerimeterHalfExtents } from "./digit-ring";

describe("digit ring geometry", () => {
  it("builds a deterministic numeric square perimeter without an outline", () => {
    const first = createDigitRingPoints(48, 17);
    const second = createDigitRingPoints(48, 17);

    expect(first).toEqual(second);
    expect(first).toHaveLength(48);
    for (const point of first) {
      expect(point.glyph).toMatch(/^[0-9]$/u);
      expect(Number.isFinite(point.angle)).toBe(true);
      expect(Math.max(Math.abs(point.x), Math.abs(point.y))).toBeCloseTo(1, 5);
      expect([0, Math.PI / 2]).toContain(point.rotation);
      expect(point.weight).toBeGreaterThan(0);
    }
  });

  it("clamps invalid counts to one point", () => {
    expect(createDigitRingPoints(0)).toHaveLength(1);
    expect(createDigitRingPoints(-4)).toHaveLength(1);
    expect(createDigitRingPoints(2.9)).toHaveLength(2);
  });

  it("keeps the stage aspect ratio for a tight rectangular perimeter", () => {
    const extents = digitPerimeterHalfExtents(1200, 600, 48);
    expect(extents.x).toBeGreaterThan(extents.y);
    expect(extents.x).toBeLessThan(1200 / 2);
    expect(extents.y).toBeLessThan(600 / 2);
  });
});
