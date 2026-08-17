export interface Persona {
  name: string;
  glyph: string;
  tagline: string;
}

const LEGACY_PERSONA_NAMES = ["筑间", "蕨", "青禾", "澄", "汐", "阿古"];

export const PERSONAS: Record<string, Persona> = {
  architecture: { name: "ARCHITECTURE", glyph: "01", tagline: "构造视角：表达代理量的相对层次。" },
  biota: { name: "BIOTA", glyph: "37", tagline: "生长视角：表达连续、缓慢的代理量变化。" },
  feng_shui: { name: "FENG_SHUI", glyph: "08", tagline: "流动视角：表达活动变化的节奏。" },
  psyche: { name: "PSYCHE", glyph: "22", tagline: "栖息视角：表达空间代理量趋于稳定。" },
  soundscape: { name: "SOUNDSCAPE", glyph: "56", tagline: "声息视角：把代理量变化转成声景。" },
  skeptic: { name: "SKEPTIC", glyph: "?", tagline: "怀疑视角：证据不足时保持未知。" },
  fusion: { name: "FUSION", glyph: "Σ", tagline: "回声视角：调用本机确认过的视觉书签。" },
};

export function personaFor(role: string): Persona {
  return PERSONAS[role] ?? { name: role, glyph: "•", tagline: "" };
}

/** Keep persona copy descriptive without exposing the old Chinese aliases. */
export function withoutPersonaNames(text: string): string {
  return [...LEGACY_PERSONA_NAMES, ...Object.values(PERSONAS).map((persona) => persona.name)]
    .filter(Boolean)
    .reduce((copy, name) => copy.split(name).join("该视角"), text)
    .replace(/([·•]\s*)?合(?=(?:的读法|[）)]))/g, "$1该视角")
    .replace(/隐喻解读\s*[·•]\s*该视角/g, "隐喻解读");
}
