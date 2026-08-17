import { describe, expect, it } from "vitest";
import {
  createThemePoints,
  DEFAULT_DIGIT_COUNT,
  nextSpatialTheme,
  SPATIAL_THEME_IDS,
  spatialTheme,
} from "./spatial-themes";

describe("spatial themes", () => {
  it("builds deterministic finite point fields for every theme", () => {
    for (const id of SPATIAL_THEME_IDS) {
      const first = createThemePoints(id);
      const second = createThemePoints(id);
      expect(first).toEqual(second);
      expect(first).toHaveLength(DEFAULT_DIGIT_COUNT);
      for (const point of first) {
        expect(Number.isFinite(point.x)).toBe(true);
        expect(Number.isFinite(point.y)).toBe(true);
        expect(Number.isFinite(point.z)).toBe(true);
        expect(Math.abs(point.x)).toBeLessThanOrEqual(2);
        expect(Math.abs(point.y)).toBeLessThanOrEqual(2);
        expect(Math.abs(point.z)).toBeLessThanOrEqual(2);
        expect(point.glyph).toMatch(/[0-9:+\-·]/u);
      }
    }
  });

  it("keeps all plan, volume, and furniture silhouettes structurally distinct", () => {
    const signatures = SPATIAL_THEME_IDS.map((id) =>
      createThemePoints(id, 96)
        .reduce(
          (sum, point, index) =>
            sum + point.x * (index + 1) + point.y * 3.1 + point.z * 7.3,
          0,
        )
        .toFixed(4),
    );
    expect(new Set(signatures).size).toBe(SPATIAL_THEME_IDS.length);
  });

  it("raises the same floor-plan samples into a spatial volume", () => {
    const plan = createThemePoints("floorplan", 120);
    const volume = createThemePoints("volume", 120);
    for (let index = 0; index < plan.length; index += 1) {
      expect(volume[index].x).toBeCloseTo(plan[index].x, 8);
      expect(volume[index].y).toBeCloseTo(plan[index].y, 8);
      expect(plan[index].z).toBe(0);
    }
    expect(volume.some((point) => point.z > 0.4)).toBe(true);
  });

  it("builds legible sofa and offset floor-lamp furniture grammars", () => {
    const sofa = createThemePoints("sofa", 720);
    const sofaX = sofa.map((point) => point.x);
    const sofaY = sofa.map((point) => point.y);
    expect(Math.max(...sofaX) - Math.min(...sofaX)).toBeGreaterThan(1.5);
    expect(Math.max(...sofaY) - Math.min(...sofaY)).toBeGreaterThan(1.2);
    expect(sofa.filter((point) => point.y > 0.42).length).toBeGreaterThan(75);

    const lamp = createThemePoints("floor_lamp", 720);
    expect(
      lamp.filter(
        (point) => Math.abs(point.x + 0.4) < 0.08 && point.y > -0.55 && point.y < 0.55,
      ).length,
    ).toBeGreaterThan(100);
    expect(lamp.filter((point) => point.x > -0.05 && point.y > 0.34).length).toBeGreaterThan(120);
    expect(lamp.filter((point) => point.y < -0.56).length).toBeGreaterThan(90);
  });

  it("keeps abstract presence explicitly non-anthropomorphic", () => {
    const field = createThemePoints("abstract_presence", 720);
    const x = field.map((point) => point.x);
    const y = field.map((point) => point.y);
    const z = field.map((point) => point.z);
    expect(Math.max(...x) - Math.min(...x)).toBeGreaterThan(1.1);
    expect(Math.max(...y) - Math.min(...y)).toBeGreaterThan(0.8);
    expect(Math.max(...z) - Math.min(...z)).toBeGreaterThan(0.55);
    expect(spatialTheme("abstract_presence").description).toMatch(
      /非拟人.*不表示人物.*姿态.*身份/u,
    );
  });

  it("cycles themes in both directions", () => {
    expect(nextSpatialTheme("floorplan")).toBe("volume");
    expect(nextSpatialTheme("floorplan", -1)).toBe(SPATIAL_THEME_IDS.at(-1));
  });
});
