export interface DigitRingPoint {
  angle: number;
  x: number;
  y: number;
  rotation: number;
  glyph: string;
  phase: number;
  weight: number;
}

/**
 * Deterministic positions for a numeric square perimeter. The perimeter is a
 * presentation layer only: it receives motion/quality parameters at draw time and never
 * writes back to the measured signal or council result.
 */
export function createDigitRingPoints(count: number, seed = 0): DigitRingPoint[] {
  const safeCount = Math.max(1, Math.floor(count));
  const safeSeed = Math.abs(Math.trunc(seed));
  return Array.from({ length: safeCount }, (_, index) => {
    const progress = (index / safeCount) * 4;
    const side = Math.floor(progress) % 4;
    const sideProgress = progress - Math.floor(progress);
    const points = [
      { x: -1 + sideProgress * 2, y: -1, rotation: 0 },
      { x: 1, y: -1 + sideProgress * 2, rotation: Math.PI / 2 },
      { x: 1 - sideProgress * 2, y: 1, rotation: 0 },
      { x: -1, y: 1 - sideProgress * 2, rotation: Math.PI / 2 },
    ];
    const point = points[side];
    return {
      angle: Math.atan2(point.y, point.x),
      x: point.x,
      y: point.y,
      rotation: point.rotation,
      glyph: String((index * 7 + safeSeed) % 10),
      phase: (index / safeCount) * Math.PI * 2 + safeSeed * 0.07,
      weight: 0.78 + ((index + safeSeed) % 5) * 0.055,
    };
  });
}

/** Fit a rectangular perimeter inside the field with independent half-extents. */
export function digitPerimeterHalfExtents(
  width: number,
  height: number,
  fontSize: number,
  ratio = 1,
): { x: number; y: number } {
  const inset = Math.max(fontSize * 0.92, 8 * ratio);
  return {
    x: Math.max(fontSize * 1.4, width * 0.5 - inset),
    y: Math.max(fontSize * 1.4, height * 0.5 - inset),
  };
}
