import { useEffect, useState, type ReactNode } from "react";
import { ReactLenis } from "lenis/react";
import { ErrorBoundary } from "./components/ErrorBoundary";
import { AlertTray } from "./components/AlertTray";
import { LifeStateStrip } from "./components/LifeStateStrip";
import { StaleOverlay } from "./components/StaleOverlay";
import { TopBar } from "./components/TopBar";
import { navigate, useRoute } from "./lib/router";
import { StreamProvider, useStream } from "./lib/state";
import { ObserveView } from "./views/ObserveView";
import { SettingsPanel } from "./views/SettingsPanel";
import { StoryView } from "./views/StoryView";
import { PerfView } from "./views/PerfView";
import { HomeView } from "./views/HomeView";
import { MemoryView } from "./views/MemoryView";
import { WhyView } from "./views/WhyView";
import { SoundscapeEngine } from "./lib/audio";
import { mapRenderParams } from "./lib/multimodal";
import { SoundscapeContext, useSoundscape } from "./lib/audio-context";

export default function App() {
  return (
    <ErrorBoundary>
      <StreamProvider>
        <SoundscapeHost>
          <AppShell />
        </SoundscapeHost>
      </StreamProvider>
    </ErrorBoundary>
  );
}

function SoundscapeHost({ children }: { children: ReactNode }) {
  const [engine] = useState(() => new SoundscapeEngine());
  useEffect(() => () => engine.dispose(), [engine]);
  return (
    <SoundscapeContext.Provider value={engine}>
      {children}
    </SoundscapeContext.Provider>
  );
}

function AppShell() {
  const route = useRoute();
  const { state } = useStream();
  const [connectionGraceExpired, setConnectionGraceExpired] = useState(false);
  const engine = useSoundscape();
  const soundscapeResult = latestResult(state);

  useEffect(() => {
    if (!engine) {
      return;
    }
    engine.setMuted(state.settings.muted);
    const onGesture = () => engine.enable();
    window.addEventListener("pointerdown", onGesture, { once: true });
    window.addEventListener("keydown", onGesture, { once: true });
    return () => {
      window.removeEventListener("pointerdown", onGesture);
      window.removeEventListener("keydown", onGesture);
    };
  }, [engine, state.settings.muted]);

  // Audio lifecycle: fade out on pause/stop/blur, fade in on return.
  useEffect(() => {
    if (!engine) {
      return;
    }
    engine.setMuted(state.settings.muted);
    const paused = state.session?.paused === true;
    const finished = state.session?.finished === true;
    if (paused || finished) {
      engine.fadeOut();
    } else if (document.hasFocus()) {
      engine.fadeIn();
    }
  }, [engine, state.settings.muted, state.session?.paused, state.session?.finished]);

  useEffect(() => {
    if (!engine) {
      return;
    }
    const onBlur = () => engine.fadeOut();
    const onFocus = () => engine.fadeIn();
    const onVisibility = () => {
      if (document.visibilityState === "hidden") {
        engine.fadeOut();
      } else {
        engine.fadeIn();
      }
    };
    window.addEventListener("blur", onBlur);
    window.addEventListener("focus", onFocus);
    document.addEventListener("visibilitychange", onVisibility);
    return () => {
      window.removeEventListener("blur", onBlur);
      window.removeEventListener("focus", onFocus);
      document.removeEventListener("visibilitychange", onVisibility);
    };
  }, [engine]);

  // Sculpture params feed the soundscape at data rate (never blocks UI).
  useEffect(() => {
    if (!engine) {
      return;
    }
    engine.update(
      mapRenderParams({
        triplet: state.triplet,
        result: soundscapeResult,
        stale: state.stale,
        dataRateHz: 4,
      }),
    );
  }, [engine, soundscapeResult, state.triplet, state.stale]);

  useEffect(() => {
    if (state.connection !== "connecting") {
      setConnectionGraceExpired(false);
      return;
    }
    // A failed WebSocket can remain in CONNECTING for several seconds. After
    // this grace period, make the absence of live data explicit instead of
    // leaving the visual field looking deceptively live.
    const timer = window.setTimeout(() => setConnectionGraceExpired(true), 1800);
    return () => window.clearTimeout(timer);
  }, [state.connection]);

  useEffect(() => {
    const root = document.documentElement;
    root.classList.toggle("reduced-motion", state.settings.reducedMotion);
    root.classList.toggle("high-contrast", state.settings.highContrast);
    root.classList.toggle("debug-mode", state.settings.debug);
  }, [state.settings]);

  useEffect(() => {
    window.scrollTo({ top: 0, left: 0, behavior: "auto" });
  }, [route]);

  const fixedPresentation = route === "story" || route === "perf";
  const staleReason = fixedPresentation
    ? null
    : state.connection === "offline" ||
        (state.connection === "connecting" && connectionGraceExpired && !state.session) ||
        (state.connection === "online" && !state.session && !state.triplet)
      ? "offline"
      : state.session?.paused
        ? "paused"
        : state.session?.finished
          ? "finished"
          : null;

  return (
    <ReactLenis
      root
      options={{
        autoRaf: true,
        anchors: true,
        lerp: state.settings.reducedMotion ? 1 : 0.1,
        smoothWheel: !state.settings.reducedMotion,
        syncTouch: false,
        respectReducedMotion: true,
        stopInertiaOnNavigate: true,
      }}
    >
      <div className={`app-shell route-${route}`}>
        <TopBar route={route} onNavigate={navigate} />
        {staleReason && route !== "home" && <StaleOverlay reason={staleReason} />}
        <AlertTray alerts={state.alerts} />
        <main className="app-main" role="main">
          {route === "home" && <HomeView />}
          {route === "observe" && <ObserveView now={Date.now()} />}
          {route === "council" && <WhyView />}
          {route === "evidence" && <WhyView evidenceFirst />}
          {route === "replay" && <MemoryView />}
          {route === "story" && <StoryView />}
          {route === "perf" && <PerfView />}
          {route === "settings" && <SettingsPanel />}
        </main>
        <footer className="app-footer">
          <LifeStateStrip />
        </footer>
      </div>
    </ReactLenis>
  );
}

function latestResult(
  state: ReturnType<typeof useStream>["state"],
): ReturnType<typeof useStream>["state"]["council"]["cycles"][string]["result"] {
  const order = state.council.order;
  for (let index = order.length - 1; index >= 0; index -= 1) {
    const cycle = state.council.cycles[order[index]];
    if (cycle?.result) {
      return cycle.result;
    }
  }
  return null;
}
