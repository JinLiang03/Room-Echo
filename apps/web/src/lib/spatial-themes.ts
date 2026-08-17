export const DIGIT_FIELD_VERSION = "digit-field-v1";
export const DEFAULT_DIGIT_COUNT = 360;

export const SPATIAL_THEME_IDS = [
  "floorplan",
  "volume",
  "lounge",
  "sofa",
  "studio",
  "floor_lamp",
  "passage",
  "garden",
  "atrium",
  "abstract_presence",
] as const;

export type SpatialThemeId = (typeof SPATIAL_THEME_IDS)[number];

export interface SpatialTheme {
  id: SpatialThemeId;
  label: string;
  name: string;
  agentRole:
    | "psyche"
    | "architecture"
    | "feng_shui"
    | "biota"
    | "soundscape"
    | "fusion";
  accent: string;
  description: string;
}

export interface SpatialPoint {
  x: number;
  y: number;
  z: number;
  glyph: string;
  phase: number;
  weight: number;
}

export const SPATIAL_THEMES: readonly SpatialTheme[] = [
  {
    id: "floorplan",
    label: "PLAN",
    name: "户型",
    agentRole: "architecture",
    accent: "#2457d6",
    description: "用户配置的艺术化户型外壳；不是 WiFi 识别或重建的真实户型。",
  },
  {
    id: "volume",
    label: "VOLUME",
    name: "构造",
    agentRole: "fusion",
    accent: "#6c63ff",
    description: "从户型外壳抬升出的生成式空间体；不表示真实三维重建。",
  },
  {
    id: "lounge",
    label: "LOUNGE",
    name: "栖息",
    agentRole: "psyche",
    accent: "#ff7f73",
    description: "弧面座椅主题；仅是可选视觉形态。",
  },
  {
    id: "sofa",
    label: "SOFA",
    name: "柔栖",
    agentRole: "psyche",
    accent: "#ef7d72",
    description: "宽幅沙发式生成外壳；是数字生命的视觉身体，不表示现场检测到沙发。",
  },
  {
    id: "studio",
    label: "STUDIO",
    name: "筑台",
    agentRole: "architecture",
    accent: "#2457d6",
    description: "桌面与灯架主题；不表示现场检测到家具。",
  },
  {
    id: "floor_lamp",
    label: "LAMP",
    name: "灯息",
    agentRole: "soundscape",
    accent: "#e9b949",
    description: "偏心落地灯式生成外壳；仅表达数字生命状态，不表示现场检测到灯具。",
  },
  {
    id: "passage",
    label: "PASSAGE",
    name: "明径",
    agentRole: "feng_shui",
    accent: "#dda72d",
    description: "拱门与台阶主题；用来观看相同信号的另一种形态。",
  },
  {
    id: "garden",
    label: "GARDEN",
    name: "蕨园",
    agentRole: "biota",
    accent: "#43aa94",
    description: "花槽与枝叶主题；是生成视觉，不是物种识别。",
  },
  {
    id: "atrium",
    label: "ATRIUM",
    name: "回声庭",
    agentRole: "soundscape",
    accent: "#7765cf",
    description: "穹顶与回声柱主题；不代表空间几何重建。",
  },
  {
    id: "abstract_presence",
    label: "FIELD",
    name: "流形",
    agentRole: "fusion",
    accent: "#c445b8",
    description: "非拟人的不规则数字流形；不表示人物、人体、姿态、身份或现场物体识别。",
  },
] as const;

const GLYPHS = "001122334455667788990123456789:+-·";
const THEME_SALTS: Record<SpatialThemeId, number> = {
  floorplan: 0x2f19,
  volume: 0x3d71,
  lounge: 0x10a6,
  sofa: 0x6a2d,
  studio: 0x57d1,
  floor_lamp: 0x7c43,
  passage: 0x9a55,
  garden: 0xc4b7,
  atrium: 0xe319,
  abstract_presence: 0xb62f,
};

export function spatialTheme(id: SpatialThemeId): SpatialTheme {
  return SPATIAL_THEMES.find((theme) => theme.id === id) ?? SPATIAL_THEMES[0];
}

export function createThemePoints(
  id: SpatialThemeId,
  count = DEFAULT_DIGIT_COUNT,
): SpatialPoint[] {
  const safeCount = Math.max(24, Math.floor(count));
  const salt = THEME_SALTS[id];
  // The plan and its volume share the same XY sample for every particle so
  // the walls visibly rise instead of shuffling between unrelated segments.
  const coordinateSalt = id === "volume" ? THEME_SALTS.floorplan : salt;
  return Array.from({ length: safeCount }, (_, index) => {
    const pick = hash01(index, coordinateSalt);
    const u = hash01(index, coordinateSalt + 1);
    const v = hash01(index, coordinateSalt + 2);
    const w = hash01(index, coordinateSalt + 3);
    const point = pointForTheme(id, pick, u, v, w);
    return {
      ...point,
      glyph: GLYPHS[(index * 7 + salt) % GLYPHS.length],
      phase: hash01(index, salt + 4) * Math.PI * 2,
      weight: 0.72 + hash01(index, salt + 5) * 0.56,
    };
  });
}

export function nextSpatialTheme(id: SpatialThemeId, direction = 1): SpatialThemeId {
  const index = SPATIAL_THEME_IDS.indexOf(id);
  const next = (index + direction + SPATIAL_THEME_IDS.length) % SPATIAL_THEME_IDS.length;
  return SPATIAL_THEME_IDS[next];
}

function pointForTheme(
  id: SpatialThemeId,
  pick: number,
  u: number,
  v: number,
  w: number,
): Pick<SpatialPoint, "x" | "y" | "z"> {
  switch (id) {
    case "floorplan":
      return floorplanPoint(pick, u, v, w);
    case "volume":
      return volumePoint(pick, u, v, w);
    case "lounge":
      return loungePoint(pick, u, v, w);
    case "sofa":
      return sofaPoint(pick, u, v, w);
    case "studio":
      return studioPoint(pick, u, v, w);
    case "floor_lamp":
      return floorLampPoint(pick, u, v, w);
    case "passage":
      return passagePoint(pick, u, v, w);
    case "garden":
      return gardenPoint(pick, u, v, w);
    case "atrium":
      return atriumPoint(pick, u, v, w);
    case "abstract_presence":
      return abstractPresencePoint(pick, u, v, w);
  }
}

type Segment3 = readonly [number, number, number, number, number, number];

const FLOORPLAN_SEGMENTS: readonly Segment3[] = [
  [-0.82, -0.62, 0, 0.82, -0.62, 0],
  [0.82, -0.62, 0, 0.82, 0.62, 0],
  [0.82, 0.62, 0, -0.82, 0.62, 0],
  [-0.82, 0.62, 0, -0.82, -0.62, 0],
  [-0.18, -0.62, 0, -0.18, 0.18, 0],
  [-0.18, 0.18, 0, 0.82, 0.18, 0],
  [0.34, 0.18, 0, 0.34, 0.62, 0],
  [-0.82, -0.08, 0, -0.18, -0.08, 0],
  [0.08, -0.62, 0, 0.08, -0.28, 0],
] as const;

function floorplanPoint(_pick: number, u: number, v: number, w: number) {
  const point = pointOnSegments(FLOORPLAN_SEGMENTS, u, v);
  return {
    ...point,
    z: w * 0,
  };
}

function volumePoint(_pick: number, u: number, v: number, w: number) {
  const point = pointOnSegments(FLOORPLAN_SEGMENTS, u, v);
  return {
    x: point.x,
    y: point.y,
    z: w * 0.68,
  };
}

function pointOnSegments(
  segments: readonly Segment3[],
  selector: number,
  progress: number,
): Pick<SpatialPoint, "x" | "y" | "z"> {
  // Sample by wall length rather than giving every segment the same number of
  // digits. Long walls stay continuous and short door/divider segments remain
  // legible, so the plan reads as a shape instead of a noisy equal-weight grid.
  const lengths = segments.map(([x1, y1, z1, x2, y2, z2]) =>
    Math.hypot(x2 - x1, y2 - y1, z2 - z1),
  );
  const totalLength = lengths.reduce((sum, length) => sum + length, 0);
  let distance = Math.max(0, Math.min(1, selector)) * totalLength;
  let scaled = segments.length - 1;
  let offset = 0;
  for (let index = 0; index < lengths.length; index += 1) {
    if (distance <= lengths[index] || index === lengths.length - 1) {
      scaled = index;
      offset = lengths[index] > 0 ? distance / lengths[index] : 0;
      break;
    }
    distance -= lengths[index];
  }
  const [x1, y1, z1, x2, y2, z2] = segments[scaled];
  const t = Math.max(0, Math.min(1, offset + (progress - 0.5) * 0.025));
  return {
    x: x1 + (x2 - x1) * t,
    y: y1 + (y2 - y1) * t,
    z: z1 + (z2 - z1) * t,
  };
}

function loungePoint(pick: number, u: number, v: number, w: number) {
  if (pick < 0.34) {
    const x = (u - 0.5) * 1.28;
    const z = (v - 0.5) * 0.78;
    return { x, y: 0.02 - 0.09 * (x * x + z * z), z };
  }
  if (pick < 0.64) {
    const x = (u - 0.5) * 1.24;
    const y = 0.02 + v * 0.94;
    const bow = 0.12 * Math.cos(x * Math.PI * 0.75);
    return { x, y, z: 0.34 + bow + (w - 0.5) * 0.05 };
  }
  if (pick < 0.82) {
    const leg = Math.floor(u * 4);
    const x = leg % 2 === 0 ? -0.54 : 0.54;
    const z = leg < 2 ? -0.28 : 0.28;
    return { x: x + (w - 0.5) * 0.05, y: -0.04 - v * 0.66, z };
  }
  if (pick < 0.94) {
    const side = u < 0.5 ? -1 : 1;
    return {
      x: side * 0.66,
      y: 0.1 + v * 0.28,
      z: (w - 0.5) * 0.7,
    };
  }
  return {
    x: (u - 0.5) * 1.42,
    y: -0.62 + (w - 0.5) * 0.03,
    z: (v - 0.5) * 0.92,
  };
}

function sofaPoint(pick: number, u: number, v: number, w: number) {
  if (pick < 0.34) {
    return {
      x: (u - 0.5) * 1.58,
      y: -0.08 + (w - 0.5) * 0.1,
      z: (v - 0.5) * 0.82,
    };
  }
  if (pick < 0.62) {
    return {
      x: (u - 0.5) * 1.56,
      y: 0.02 + v * 0.72,
      z: 0.36 + (w - 0.5) * 0.09,
    };
  }
  if (pick < 0.79) {
    const side = u < 0.5 ? -1 : 1;
    return {
      x: side * 0.83 + (w - 0.5) * 0.06,
      y: -0.1 + v * 0.43,
      z: (hashBand(u + v * 0.17) - 0.5) * 0.8,
    };
  }
  if (pick < 0.93) {
    const seam = Math.floor(u * 3) - 1;
    return {
      x: seam * 0.5 + (w - 0.5) * 0.025,
      y: -0.03 + v * 0.14,
      z: (v - 0.5) * 0.72,
    };
  }
  const leg = Math.floor(u * 4);
  return {
    x: leg % 2 === 0 ? -0.67 : 0.67,
    y: -0.12 - v * 0.48,
    z: leg < 2 ? -0.3 : 0.3,
  };
}

function studioPoint(pick: number, u: number, v: number, w: number) {
  if (pick < 0.48) {
    return {
      x: (u - 0.5) * 1.45,
      y: 0.2 + (w - 0.5) * 0.04,
      z: (v - 0.5) * 0.82,
    };
  }
  if (pick < 0.7) {
    const leg = Math.floor(u * 4);
    return {
      x: (leg % 2 === 0 ? -0.62 : 0.62) + (w - 0.5) * 0.05,
      y: 0.18 - v * 0.78,
      z: leg < 2 ? -0.32 : 0.32,
    };
  }
  if (pick < 0.86) {
    if (u < 0.58) {
      return { x: -0.42, y: 0.24 + v * 0.78, z: 0.02 };
    }
    const angle = v * Math.PI * 2;
    return {
      x: -0.42 + Math.cos(angle) * 0.22 * w,
      y: 1.02 - Math.abs(Math.sin(angle)) * 0.18 * w,
      z: Math.sin(angle) * 0.18 * w,
    };
  }
  const angle = u * Math.PI * 2;
  return {
    x: 0.48 + Math.cos(angle) * 0.2,
    y: -0.18 + v * 0.38,
    z: -0.02 + Math.sin(angle) * 0.2,
  };
}

function floorLampPoint(pick: number, u: number, v: number, w: number) {
  if (pick < 0.27) {
    return {
      x: -0.4 + (w - 0.5) * 0.025,
      y: -0.58 + v * 1.14,
      z: (u - 0.5) * 0.035,
    };
  }
  if (pick < 0.45) {
    const t = v;
    return {
      x: -0.4 + t * 0.72,
      y: 0.54 + Math.sin(t * Math.PI * 0.5) * 0.25,
      z: (w - 0.5) * 0.06,
    };
  }
  if (pick < 0.74) {
    const theta = u * Math.PI * 2;
    const radius = 0.07 + v * 0.3;
    return {
      x: 0.34 + Math.cos(theta) * radius,
      y: 0.73 - v * 0.36,
      z: Math.sin(theta) * radius,
    };
  }
  if (pick < 0.93) {
    const theta = u * Math.PI * 2;
    const radius = 0.08 + Math.sqrt(v) * 0.27;
    return {
      x: -0.4 + Math.cos(theta) * radius,
      y: -0.61 + (w - 0.5) * 0.025,
      z: Math.sin(theta) * radius,
    };
  }
  const theta = u * Math.PI * 2;
  return {
    x: 0.34 + Math.cos(theta) * 0.4,
    y: 0.31 + (w - 0.5) * 0.04,
    z: Math.sin(theta) * 0.4,
  };
}

function passagePoint(pick: number, u: number, v: number, w: number) {
  if (pick < 0.38) {
    const side = u < 0.5 ? -1 : 1;
    return {
      x: side * (0.5 + w * 0.12),
      y: -0.5 + v * 1.05,
      z: (hashBand(u) - 0.5) * 0.48,
    };
  }
  if (pick < 0.65) {
    const angle = Math.PI * u;
    const radius = 0.5 + w * 0.12;
    return {
      x: Math.cos(angle) * radius,
      y: 0.54 + Math.sin(angle) * radius,
      z: (v - 0.5) * 0.48,
    };
  }
  if (pick < 0.88) {
    const step = Math.floor(u * 4);
    return {
      x: (v - 0.5) * (0.86 - step * 0.08),
      y: -0.5 + step * 0.11,
      z: -0.48 + step * 0.2 + w * 0.16,
    };
  }
  return {
    x: (u - 0.5) * 1.5,
    y: -0.52,
    z: (v - 0.5) * 1.14,
  };
}

function gardenPoint(pick: number, u: number, v: number, w: number) {
  const bed = Math.floor(u * 3);
  const bedX = (bed - 1) * 0.52;
  if (pick < 0.34) {
    const side = Math.floor(v * 4);
    const along = w - 0.5;
    return {
      x: bedX + (side < 2 ? along * 0.42 : (side % 2 ? 0.21 : -0.21)),
      y: -0.44 + (side < 2 ? (side === 0 ? 0 : 0.18) : v * 0.18),
      z: side < 2 ? (v - 0.5) * 0.34 : along * 0.34,
    };
  }
  if (pick < 0.78) {
    const stem = Math.floor(u * 7);
    const baseX = (stem / 6 - 0.5) * 1.28;
    const height = 0.46 + hashBand(u) * 0.48;
    const sway = Math.sin(v * Math.PI * 1.4 + stem) * 0.1 * v;
    return {
      x: baseX + sway,
      y: -0.28 + v * height,
      z: (w - 0.5) * 0.38,
    };
  }
  if (pick < 0.94) {
    const angle = v * Math.PI * 2;
    const cluster = Math.floor(u * 6);
    return {
      x: (cluster / 5 - 0.5) * 1.18 + Math.cos(angle) * 0.16 * w,
      y: 0.22 + hashBand(u) * 0.52 + Math.sin(angle) * 0.08 * w,
      z: Math.sin(angle) * 0.2 * w,
    };
  }
  return { x: (u - 0.5) * 1.65, y: -0.48, z: (v - 0.5) * 0.94 };
}

function atriumPoint(pick: number, u: number, v: number, w: number) {
  if (pick < 0.5) {
    const theta = u * Math.PI * 2;
    const phi = v * Math.PI * 0.5;
    const radius = 0.68 + (w - 0.5) * 0.08;
    return {
      x: Math.cos(theta) * Math.sin(phi) * radius,
      y: 0.02 + Math.cos(phi) * 0.92,
      z: Math.sin(theta) * Math.sin(phi) * radius,
    };
  }
  if (pick < 0.72) {
    const column = Math.floor(u * 8);
    const angle = (column / 8) * Math.PI * 2;
    return {
      x: Math.cos(angle) * 0.66,
      y: -0.58 + v * 0.62,
      z: Math.sin(angle) * 0.66,
    };
  }
  if (pick < 0.9) {
    const angle = u * Math.PI * 2;
    const ring = 0.3 + Math.floor(v * 3) * 0.18;
    return {
      x: Math.cos(angle) * ring,
      y: 0.02 + (0.66 - ring) * 0.9,
      z: Math.sin(angle) * ring,
    };
  }
  return {
    x: (u - 0.5) * 1.5,
    y: -0.58,
    z: (v - 0.5) * 1.1,
  };
}

/**
 * Three irregular lobes and short filaments form a deliberately
 * non-anthropomorphic field. Points fill a changing cloud instead of tracing
 * a closed rectangle, ring, or standing-axis grammar.
 */
function abstractPresencePoint(pick: number, u: number, v: number, w: number) {
  const lobe = Math.min(2, Math.floor(pick * 3));
  const phase = [0.18, 2.24, 4.36][lobe];
  const centerX = [-0.38, 0.18, 0.34][lobe];
  const centerY = [0.2, -0.2, 0.16][lobe];
  const radiusX = [0.56, 0.48, 0.38][lobe];
  const radiusY = [0.42, 0.5, 0.34][lobe];
  const theta = u * Math.PI * 2 + phase;
  const radial = 0.18 + v * 0.72;
  const wobble =
    0.74 +
    Math.sin(theta * 3 + phase) * 0.17 +
    Math.sin(theta * 5 - phase) * 0.1;
  return {
    x:
      centerX +
      Math.cos(theta) * radiusX * radial * wobble +
      Math.sin(theta * 2 + phase) * 0.1 +
      (v - 0.5) * 0.08,
    y:
      centerY +
      Math.sin(theta) * radiusY * radial * wobble +
      Math.cos(theta * 3 + phase) * 0.08 +
      (v - 0.5) * 0.06,
    z:
      (w - 0.5) * 0.58 +
      Math.sin(theta * 2 + phase) * (0.16 + lobe * 0.04) +
      Math.cos(theta * 3 - phase) * 0.05,
  };
}

function hashBand(value: number): number {
  return (value * 7.137) % 1;
}

function hash01(index: number, salt: number): number {
  let value = Math.imul(index + 1, 0x9e3779b1) ^ salt;
  value = Math.imul(value ^ (value >>> 16), 0x21f0aaad);
  value = Math.imul(value ^ (value >>> 15), 0x735a2d97);
  value ^= value >>> 15;
  return (value >>> 0) / 4294967295;
}
