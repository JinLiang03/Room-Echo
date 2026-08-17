export interface DigitGeometryPoint {
  x: number;
  y: number;
  z: number;
  glyph: string;
  phase: number;
}

export type DigitRole =
  | "architecture"
  | "biota"
  | "feng_shui"
  | "psyche"
  | "soundscape"
  | "skeptic"
  | "fusion";

type Segment = readonly [number, number, number, number];

const GLYPHS = "00112233445566778899:+-·";

/**
 * Small line grammars keep the agent visuals legible without turning them into
 * sensor claims. They are visual metaphors for a role, not object detection.
 */
export function segmentsForRole(role: string): readonly Segment[] {
  switch (role as DigitRole) {
    case "architecture":
      return [
        [-0.72, 0.5, 0.72, 0.5],
        [-0.62, 0.5, -0.62, -0.26],
        [0.62, 0.5, 0.62, -0.26],
        [-0.62, -0.26, 0, -0.78],
        [0, -0.78, 0.62, -0.26],
        [-0.38, 0.5, -0.38, 0.08],
        [0.38, 0.5, 0.38, 0.08],
      ];
    case "biota":
      return [
        [0, 0.74, 0, -0.72],
        [0, 0.18, -0.58, -0.18],
        [0, -0.08, 0.58, -0.4],
        [-0.58, -0.18, -0.9, -0.52],
        [0.58, -0.4, 0.86, -0.72],
        [-0.28, 0.24, -0.5, 0.5],
        [0.28, 0.04, 0.58, 0.27],
      ];
    case "feng_shui":
      return [
        [-0.72, 0.56, -0.72, -0.06],
        [-0.72, -0.06, -0.52, -0.54],
        [-0.52, -0.54, 0, -0.72],
        [0, -0.72, 0.52, -0.54],
        [0.52, -0.54, 0.72, -0.06],
        [0.72, -0.06, 0.72, 0.56],
        [-0.48, 0.42, 0.48, 0.42],
      ];
    case "psyche":
      return [
        [-0.62, 0.58, -0.62, -0.18],
        [-0.62, -0.18, -0.34, -0.42],
        [-0.34, -0.42, 0.36, -0.42],
        [0.36, -0.42, 0.62, -0.18],
        [0.62, -0.18, 0.62, 0.58],
        [-0.62, -0.18, 0.62, -0.18],
        [-0.9, -0.62, -0.52, -0.62],
        [0.52, -0.62, 0.9, -0.62],
      ];
    case "soundscape":
      return [
        [-0.9, 0.5, -0.6, -0.42],
        [-0.6, -0.42, -0.22, 0.5],
        [-0.22, 0.5, 0.16, -0.42],
        [0.16, -0.42, 0.54, 0.5],
        [0.54, 0.5, 0.9, -0.42],
        [-0.76, 0.62, 0.76, 0.62],
      ];
    case "skeptic":
      return [
        [-0.36, -0.68, 0.36, -0.68],
        [-0.36, -0.68, -0.62, -0.14],
        [-0.62, -0.14, -0.38, 0.2],
        [-0.38, 0.2, 0.38, 0.2],
        [0.38, 0.2, 0.62, -0.14],
        [0.62, -0.14, 0.36, -0.68],
        [0, 0.36, 0, 0.62],
      ];
    case "fusion":
      return [
        [-0.72, -0.48, -0.28, 0.42],
        [-0.28, 0.42, 0.18, -0.48],
        [0.18, -0.48, 0.62, 0.42],
        [-0.82, 0.02, 0.76, 0.02],
        [-0.58, -0.72, 0.58, -0.72],
      ];
    default:
      return segmentsForRole("fusion");
  }
}

export const HOUSE_SEGMENTS: readonly Segment[] = [
  [-0.76, 0.34, -0.76, -0.46],
  [-0.76, -0.46, 0.76, -0.46],
  [0.76, -0.46, 0.76, 0.34],
  [-0.9, 0.34, 0, 0.9],
  [0, 0.9, 0.9, 0.34],
  [-0.76, 0.08, 0.76, 0.08],
  [-0.42, 0.08, -0.42, -0.46],
  [0.42, 0.08, 0.42, -0.46],
  [-0.22, -0.46, -0.22, -0.02],
  [-0.22, -0.02, 0.22, -0.02],
  [0.22, -0.02, 0.22, -0.46],
  [-0.57, 0.22, -0.34, 0.22],
  [-0.34, 0.22, -0.34, 0.02],
  [-0.34, 0.02, -0.57, 0.02],
  [-0.57, 0.02, -0.57, 0.22],
  [0.34, 0.22, 0.57, 0.22],
  [0.57, 0.22, 0.57, 0.02],
  [0.57, 0.02, 0.34, 0.02],
  [0.34, 0.02, 0.34, 0.22],
  [-0.9, -0.56, 0.9, -0.56],
];

export function sampleDigitGeometry(
  segments: readonly Segment[],
  count: number,
  seed: number,
): DigitGeometryPoint[] {
  const safeCount = Math.max(24, Math.floor(count));
  return Array.from({ length: safeCount }, (_, index) => {
    const segment = segments[index % segments.length];
    const t = hash01(index, seed + 1);
    const jitter = (hash01(index, seed + 2) - 0.5) * 0.025;
    return {
      x: segment[0] + (segment[2] - segment[0]) * t + jitter,
      y: segment[1] + (segment[3] - segment[1]) * t + jitter,
      z: (hash01(index, seed + 3) - 0.5) * 0.8,
      glyph: GLYPHS[(index * 11 + seed) % GLYPHS.length],
      phase: hash01(index, seed + 4) * Math.PI * 2,
    };
  });
}

export function hash01(index: number, salt: number): number {
  let value = Math.imul(index + 1, 0x9e3779b1) ^ salt;
  value = Math.imul(value ^ (value >>> 16), 0x21f0aaad);
  value = Math.imul(value ^ (value >>> 15), 0x735a2d97);
  value ^= value >>> 15;
  return (value >>> 0) / 4294967295;
}
