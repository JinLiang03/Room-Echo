import { useEffect, useRef, useState } from "react";
import { AgentActionWindow } from "../components/AgentActionWindow";
import { DigitMorphField } from "../components/DigitMorphField";
import { RoomEchoAgentPanel } from "../components/RoomEchoAgentPanel";
import { publicAgentPresentation } from "../lib/agent-presentation";
import {
  careSuggestions,
  supportedCareMoment,
  waitingCareSuggestions,
} from "../lib/care";
import { useCareScenario } from "../lib/care-state";
import {
  deriveLifeState,
  lifeStateDefinition,
  type LifeStateId,
} from "../lib/life-state";
import {
  findEchoMemory,
  readLifeMemories,
  saveLifeMemory,
} from "../lib/memories";
import { themeForAgentResult } from "../lib/agent-visual-theme";
import { navigate } from "../lib/router";
import { useStream } from "../lib/state";
import type { CouncilResult } from "../lib/types";

export function HomeView() {
  const { state } = useStream();
  const care = useCareScenario();
  const [memories, setMemories] = useState(readLifeMemories);
  const [savedPulse, setSavedPulse] = useState(false);
  const savedTimerRef = useRef<number | null>(null);
  const selectedCareMoment = care.enabled ? care.moment : null;
  const careMoment = supportedCareMoment(selectedCareMoment);
  const careStatus =
    care.enabled && care.status === "ready" && careMoment === null
      ? "unavailable"
      : care.status;
  const careTriplet = careMoment?.evidence_core.proxy_triplet ?? null;
  const streamVisible = state.stale ? null : state.triplet;
  const visible = care.enabled ? careTriplet : streamVisible;
  const visibleStale = care.enabled ? careTriplet === null : state.stale;
  const result = care.enabled || state.stale ? null : latestResult(state);
  const remembered = !care.enabled && findEchoMemory(visible, memories) !== null;
  const inferredState = deriveLifeState({
    triplet: visible,
    history: care.enabled ? (visible ? [visible] : []) : state.history,
    // The numeric body dynamics follow measured proxy signals. Fusion may
    // select an allowlisted generative theme, but cannot rewrite the signals.
    result: null,
    stale: visibleStale,
    remembered,
  });
  const stableState = useStableLifeState(inferredState);
  // A simulated care frame is an already sealed atomic snapshot. Keep its
  // Agent copy, action cards and field geometry on the same frame rather than
  // applying the ambient stream's presentation debounce.
  const displayedState = care.enabled ? inferredState : stableState;
  const lifeState: LifeStateId = savedPulse ? "echo" : displayedState;
  const canRemember =
    !care.enabled &&
    visible !== null &&
    visible.status !== "insufficient_signal" &&
    visible.status !== "uncalibrated";
  const theme = useAmbientLifeTheme(
    lifeState,
    result,
  );
  const agent = publicAgentPresentation(state);
  const sourceMode = state.session?.mode ?? state.sourceHealth?.source_mode ?? null;
  const actionSuggestions = care.enabled
    ? careMoment
      ? careSuggestions(careMoment)
      : waitingCareSuggestions(careStatus)
    : undefined;
  const sourceLabels = homeSourceLabels(sourceMode, care.enabled, careStatus);
  const evidenceHash = care.enabled
    ? careMoment?.evidence_hash ?? "waiting"
    : agent.evidenceHash;
  const boundSessionId = care.enabled
    ? visible?.session_id ?? "waiting"
    : visible?.session_id ?? null;
  const boundWindowId = care.enabled
    ? visible?.window_id ?? "waiting"
    : visible?.window_id ?? null;

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
    <section
      className="home-view"
      aria-label="Room Echo 此刻"
      data-care-moment={careMoment?.moment ?? "waiting"}
    >
      <aside className="room-echo-sidebar">
        <div className="room-echo-brand-row">
          <button type="button" className="room-echo-brand" onClick={() => navigate("home")}>
            <span>Room Echo</span>
            <small>空间回声</small>
          </button>
        </div>

        <nav className="room-echo-nav" aria-label="主导航">
          <button type="button" className="is-active" aria-current="page">此刻</button>
          <button type="button" onClick={() => navigate("replay")}>记忆</button>
          <button type="button" onClick={() => navigate("council")}>为什么</button>
        </nav>

        <RoomEchoAgentPanel
          agent={agent}
          careMode={care.enabled}
          careMoment={careMoment}
          careStatus={careStatus}
        />
        <AgentActionWindow
          agent={agent}
          sourceMode={care.enabled ? "mock" : sourceMode}
          suggestions={actionSuggestions}
          evidenceHash={evidenceHash}
          sessionId={boundSessionId}
          windowId={boundWindowId}
        />

        <div className="room-echo-system-note">
          <span>{sourceLabels.source}</span>
          <span>NO DEVICE EXECUTION</span>
        </div>
      </aside>

      <div className="room-echo-field">
        <header className="room-echo-field-label">
          <span>{sourceLabels.field}</span>
          <strong>{lifeStateDefinition(lifeState).label}</strong>
        </header>
        <div className="home-field-stage">
          <DigitMorphField
            theme={theme}
            triplet={visible}
            // The Agent selects a presentation theme above, while the field's
            // numeric motion parameters remain signal-only.
            result={null}
            stale={visibleStale}
            reducedMotion={state.settings.reducedMotion}
            autoMorph
            showPerimeter={false}
            fluid
            fluidMode={careMoment?.moment ?? "ambient"}
            pointCount={1200}
            debug={state.settings.debug}
            lifeState={lifeState}
            onRemember={canRemember ? rememberMoment : undefined}
            evidenceHash={evidenceHash}
          />
        </div>
        <div className="room-echo-watermark">
          <strong>INFERENCE FIELD — NOT A CAMERA IMAGE</strong>
          <span>艺术化代理信号解释，非真实影像</span>
        </div>
      </div>
    </section>
  );
}

function homeSourceLabels(
  sourceMode: string | null,
  careEnabled: boolean,
  careStatus: ReturnType<typeof useCareScenario>["status"],
): { source: string; field: string } {
  if (careEnabled) {
    if (careStatus === "loading") {
      return { source: "SIM · CARE · WAITING", field: "WIFI PROXY INFERENCE FIELD" };
    }
    if (careStatus === "unavailable") {
      return { source: "SIM · CARE · UNAVAILABLE", field: "WIFI PROXY INFERENCE FIELD" };
    }
    return { source: "SIM · CARE", field: "WIFI PROXY INFERENCE FIELD" };
  }
  if (sourceMode === "live") {
    return { source: "LIVE", field: "LIVE INFERENCE FIELD" };
  }
  if (sourceMode === "replay") {
    return { source: "SIM · REPLAY", field: "REPLAY INFERENCE FIELD" };
  }
  if (sourceMode === "mock") {
    return { source: "SIM · MOCK", field: "MOCK INFERENCE FIELD" };
  }
  return { source: "SOURCE · WAITING", field: "INFERENCE FIELD" };
}

function useAmbientLifeTheme(
  lifeState: LifeStateId,
  result: CouncilResult | null,
) {
  return themeForAgentResult(result, lifeStateDefinition(lifeState).theme);
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
