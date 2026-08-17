import { createContext, useContext } from "react";
import type { SoundscapeEngine } from "./audio";

export const SoundscapeContext = createContext<SoundscapeEngine | null>(null);

export function useSoundscape(): SoundscapeEngine | null {
  return useContext(SoundscapeContext);
}
