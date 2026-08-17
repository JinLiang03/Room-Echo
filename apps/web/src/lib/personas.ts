export interface Persona {
  name: string;
  glyph: string;
  tagline: string;
}

export const PERSONAS: Record<string, Persona> = {
  architecture: { name: "筑间", glyph: "01", tagline: "构造视角：表达代理量的相对层次。" },
  biota: { name: "蕨", glyph: "37", tagline: "生长视角：表达连续、缓慢的代理量变化。" },
  feng_shui: { name: "青禾", glyph: "08", tagline: "流动视角：表达活动变化的节奏。" },
  psyche: { name: "澄", glyph: "22", tagline: "栖息视角：表达空间代理量趋于稳定。" },
  soundscape: { name: "汐", glyph: "56", tagline: "声息视角：把代理量变化转成声景。" },
  skeptic: { name: "阿古", glyph: "?", tagline: "怀疑视角：证据不足时保持未知。" },
  fusion: { name: "合", glyph: "Σ", tagline: "回声视角：调用本机确认过的视觉书签。" },
};

export function personaFor(role: string): Persona {
  return PERSONAS[role] ?? { name: role, glyph: "•", tagline: "" };
}
