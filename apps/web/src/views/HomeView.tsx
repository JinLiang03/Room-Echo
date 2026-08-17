import { useEffect, useRef, useState } from "react";
import { DigitMorphField } from "../components/DigitMorphField";
import {
  deriveLifeState,
  lifeStateDefinition,
  lifeStateThemes,
  type LifeStateId,
} from "../lib/life-state";
import {
  findEchoMemory,
  readLifeMemories,
  saveLifeMemory,
} from "../lib/memories";
import { useStream } from "../lib/state";
import type { CouncilResult } from "../lib/types";

export function HomeView() {
  const { state } = useStream();
  const [memories, setMemories] = useState(readLifeMemories);
  const [savedPulse, setSavedPulse] = useState(false);
  const savedTimerRef = useRef<number | null>(null);
  const visible = state.stale ? null : state.triplet;
  const result = state.stale ? null : latestResult(state);
  const remembered = findEchoMemory(visible, memories) !== null;
  const inferredState = deriveLifeState({
    triplet: visible,
    history: state.history,
    result,
    stale: state.stale,
    remembered,
  });
  const stableState = useStableLifeState(inferredState);
  const lifeState: LifeStateId = savedPulse ? "echo" : stableState;
  const canRemember =
    visible !== null &&
    visible.status !== "insufficient_signal" &&
    visible.status !== "uncalibrated";
  const theme = useAmbientLifeTheme(
    lifeState,
    canRemember,
    state.settings.reducedMotion,
  );

  useEffect(
    () => () => {
      if (savedTimerRef.current !== null) window.clearTimeout(savedTimerRef.current);
    },
    [],
  );

  const rememberMoment = () => {
    if (!canRemember || !visible) return;
    const memory = saveLifeMemory({
      lifeState: inferredState,
      triplet: visible,
      result,
    });
    setMemories((current) => [memory, ...current.filter((item) => item.id !== memory.id)]);
    setSavedPulse(true);
    if (savedTimerRef.current !== null) window.clearTimeout(savedTimerRef.current);
    savedTimerRef.current = window.setTimeout(() => setSavedPulse(false), 1800);
  };

  return (
    <section className="home-view" aria-label="此刻的数字生命">
      <div className="home-field-grid">
        <div className="home-field-stage">
          <DigitMorphField
            theme={theme}
            triplet={visible}
            result={result}
            stale={state.stale}
            reducedMotion={state.settings.reducedMotion}
            autoMorph
            pointCount={900}
            debug={state.settings.debug}
            lifeState={lifeState}
            onRemember={canRemember ? rememberMoment : undefined}
          />
        </div>
      </div>
    </section>
  );
}

/**
 * Slow presentation-only rotation within the current signal-selected state.
 * The state, measurements, and confidence remain unchanged.
 */
function useAmbientLifeTheme(
  lifeState: LifeStateId,
  active: boolean,
  reducedMotion: boolean,
) {
  const variants = lifeStateThemes(lifeState);
  const [selection, setSelection] = useState({ lifeState, index: 0 });
  const selectedIndex =
    selection.lifeState === lifeState ? selection.index % variants.length : 0;

  useEffect(() => {
    setSelection({ lifeState, index: 0 });
  }, [lifeState, reducedMotion]);

  useEffect(() => {
    if (!active || reducedMotion || variants.length < 2) return;
    const timer = window.setInterval(() => {
      setSelection((current) =>
        current.lifeState === lifeState
          ? { lifeState, index: (current.index + 1) % variants.length }
          : { lifeState, index: 0 },
      );
    }, 12_000);
    return () => window.clearInterval(timer);
  }, [active, lifeState, reducedMotion, variants.length]);

  return variants[selectedIndex] ?? lifeStateDefinition(lifeState).theme;
}

function useStableLifeState(candidate: LifeStateId): LifeStateId {
  const [stable, setStable] = useState(candidate);

  useEffect(() => {
    if (candidate === stable) return;
    if (candidate === "doubt" || candidate === "echo") {
      setStable(candidate);
      return;
    }
    const delay = candidate === "flow" ? 900 : 1600;
    const timer = window.setTimeout(() => setStable(candidate), delay);
    return () => window.clearTimeout(timer);
  }, [candidate, stable]);

  return stable;
}

function latestResult(state: ReturnType<typeof useStream>["state"]): CouncilResult | null {
  for (let index = state.council.order.length - 1; index >= 0; index -= 1) {
    const cycle = state.council.cycles[state.council.order[index]];
    if (cycle?.result) {
      return cycle.result;
    }
  }
  return null;
}
