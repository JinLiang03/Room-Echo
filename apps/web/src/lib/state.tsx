import {
  createContext,
  useContext,
  useEffect,
  useMemo,
  useReducer,
  useRef,
  type ReactNode,
} from "react";
import { fetchBundles, startStream, stopStream, wsUrl } from "./api";
import type {
  AlertItem,
  CycleView,
  ReplayBundleSummary,
  SessionStatus,
  Settings,
  StreamEvent,
  StreamState,
} from "./types";
import type { SignalTriplet } from "./types";
import { HISTORY_LIMIT } from "./types";
import { StreamClient, type ConnectionStatus } from "./ws";

export const DEFAULT_SETTINGS: Settings = {
  muted: true,
  reducedMotion: false,
  highContrast: false,
  debug: false,
  showGroundTruth: false,
};

export function initialState(): StreamState {
  return {
    connection: "connecting",
    sequence: -1,
    applied: 0,
    dropped: 0,
    session: null,
    sourceHealth: null,
    triplet: null,
    history: [],
    quality: null,
    qualityHistory: [],
    council: { cycles: {}, order: [], discussionUnavailable: true },
    alerts: [],
    replay: {
      bundles: [],
      selected: null,
      verifying: null,
      error: null,
      groundTruthHidden: true,
    },
    settings: DEFAULT_SETTINGS,
    stale: false,
    lastEventAt: null,
  };
}

export type StreamAction =
  | { type: "event"; event: StreamEvent }
  | { type: "connection"; status: ConnectionStatus }
  | { type: "settings"; patch: Partial<Settings> }
  | { type: "replay-bundles"; bundles: ReplayBundleSummary[] }
  | { type: "replay-error"; error: string }
  | { type: "replay-select"; bundleId: string }
  | { type: "replay-verifying"; bundleId: string | null }
  | { type: "reset" };

let alertSeq = 0;

type SessionStatusPatch = Partial<SessionStatus>;

interface SnapshotPayload {
  status?: SessionStatusPatch | null;
  latest_triplet?: StreamState["triplet"];
  latest_result?: StreamState["council"]["cycles"][string]["result"];
  latest_source_health?: StreamState["sourceHealth"];
  source_health?: StreamState["sourceHealth"];
  recent_events?: StreamEvent[];
  catch_up?: StreamEvent[];
}

function clearSessionRuntime(state: StreamState): StreamState {
  return {
    ...state,
    sequence: -1,
    applied: 0,
    dropped: 0,
    session: null,
    sourceHealth: null,
    triplet: null,
    history: [],
    quality: null,
    qualityHistory: [],
    council: { cycles: {}, order: [], discussionUnavailable: true },
    alerts: [],
    stale: false,
    lastEventAt: null,
  };
}

function clearTimelineRuntime(state: StreamState): StreamState {
  return {
    ...state,
    triplet: null,
    history: [],
    quality: null,
    qualityHistory: [],
    council: { cycles: {}, order: [], discussionUnavailable: true },
    stale: true,
    lastEventAt: null,
  };
}

function mergeSessionStatus(
  previous: SessionStatus | null,
  patch: SessionStatusPatch,
  emittedAt?: string,
): SessionStatus | null {
  const identifiesSession =
    patch.session_id != null ||
    patch.mode != null ||
    patch.source_id != null ||
    patch.bundle_id != null ||
    patch.running !== undefined;
  if (previous === null && !identifiesSession) {
    return null;
  }

  const base: SessionStatus = previous ?? {
    running: false,
    finished: false,
    paused: false,
    rate: 1,
    position_s: 0,
    frames: 0,
    windows: 0,
    evidence_seals: 0,
    recording: false,
    recompute: false,
    updated_at: emittedAt ?? "",
  };
  const definedPatch = Object.fromEntries(
    Object.entries(patch).filter(([, value]) => value !== undefined),
  ) as SessionStatusPatch;
  const merged: SessionStatus = { ...base, ...definedPatch };

  if (patch.state === "starting") {
    merged.running = true;
    merged.finished = false;
  } else if (patch.state === "finished") {
    merged.running = false;
    merged.finished = true;
    merged.paused = false;
  } else if (patch.state === "stopped") {
    merged.running = false;
    merged.paused = false;
  } else if (patch.running === true) {
    merged.state = "running";
  }
  if (!patch.updated_at && emittedAt) {
    merged.updated_at = emittedAt;
  }
  return merged;
}

function applySessionStatus(
  state: StreamState,
  patch: SessionStatusPatch,
  emittedAt?: string,
): StreamState {
  const changedSession =
    patch.session_id != null &&
    state.session?.session_id != null &&
    patch.session_id !== state.session.session_id;
  const changedTimeline =
    !changedSession &&
    patch.timeline_revision !== undefined &&
    state.session?.timeline_revision !== undefined &&
    patch.timeline_revision !== state.session.timeline_revision;
  const next = changedSession
    ? {
        ...clearSessionRuntime(state),
        sequence: state.sequence,
        applied: state.applied,
        dropped: state.dropped,
        lastEventAt: state.lastEventAt,
      }
    : changedTimeline
      ? clearTimelineRuntime(state)
      : state;
  const session = mergeSessionStatus(next.session, patch, emittedAt);
  if (session === null) {
    return next;
  }
  const selected =
    next.replay.selected ?? session.source_id ?? session.bundle_id ?? null;
  return {
    ...next,
    session,
    stale: session.finished || session.paused || !session.running,
    replay: selected ? { ...next.replay, selected } : next.replay,
  };
}

function recoveryEvents(payload: SnapshotPayload): StreamEvent[] {
  const bySequence = new Map<number, StreamEvent>();
  const withoutSequence: StreamEvent[] = [];
  for (const recovered of [
    ...(payload.recent_events ?? []),
    ...(payload.catch_up ?? []),
  ]) {
    if (recovered.event_type === "snapshot") {
      continue;
    }
    if (recovered.sequence === undefined) {
      withoutSequence.push(recovered);
    } else {
      bySequence.set(recovered.sequence, recovered);
    }
  }
  return [
    ...[...bySequence.values()].sort(
      (left, right) => (left.sequence ?? 0) - (right.sequence ?? 0),
    ),
    ...withoutSequence,
  ];
}

function applyEvent(state: StreamState, event: StreamEvent): StreamState {
  if (event.event_type === "snapshot") {
    const payload = event.payload as SnapshotPayload;
    if (payload.status === null) {
      const cleared = clearSessionRuntime(state);
      return {
        ...cleared,
        sequence: Math.max(cleared.sequence, event.sequence ?? cleared.sequence),
      };
    }

    const incomingSessionId = payload.status?.session_id;
    const shouldReset =
      incomingSessionId != null &&
      ((state.session?.session_id != null &&
        state.session.session_id !== incomingSessionId) ||
        (state.session === null &&
          (state.triplet !== null || state.council.order.length > 0)));
    let next = shouldReset ? clearSessionRuntime(state) : { ...state };

    let recoveredSignal = false;
    for (const recovered of recoveryEvents(payload)) {
      if (
        incomingSessionId != null &&
        recovered.session_id != null &&
        recovered.session_id !== incomingSessionId
      ) {
        continue;
      }
      if (
        recovered.sequence !== undefined &&
        recovered.sequence <= next.sequence
      ) {
        continue;
      }
      next = applyEvent(next, recovered);
      recoveredSignal = recoveredSignal || recovered.event_type === "signal.frame";
    }

    const snapshotHealth = payload.latest_source_health ?? payload.source_health;
    if (snapshotHealth) {
      next = { ...next, sourceHealth: snapshotHealth };
    }
    if (payload.status) {
      next = applySessionStatus(next, payload.status, event.emitted_at);
    }
    if (
      payload.latest_triplet &&
      (!recoveredSignal || next.triplet === null) &&
      payload.latest_triplet.window_id !== next.triplet?.window_id
    ) {
      next = applyTriplet(next, payload.latest_triplet);
    }
    if (
      payload.latest_result &&
      !next.council.cycles[payload.latest_result.cycle_id]?.result
    ) {
      next = applyResult(next, payload.latest_result.cycle_id, payload.latest_result);
    }
    next = {
      ...next,
      sequence: Math.max(next.sequence, event.sequence ?? next.sequence),
    };
    return next;
  }

  const changedEventSession =
    event.session_id != null &&
    state.session?.session_id != null &&
    event.session_id !== state.session.session_id;
  if (
    !changedEventSession &&
    event.sequence !== undefined &&
    event.sequence <= state.sequence
  ) {
    return { ...state, dropped: state.dropped + 1 };
  }
  const eventState = changedEventSession ? clearSessionRuntime(state) : state;
  const next: StreamState = {
    ...eventState,
    sequence: event.sequence ?? eventState.sequence,
    applied: eventState.applied + 1,
    lastEventAt: Date.now(),
  };

  switch (event.event_type) {
    case "signal.frame": {
      const triplet = event.payload.triplet as StreamState["triplet"];
      if (!triplet) {
        return next;
      }
      return applyTriplet(next, triplet);
    }
    case "source.health":
      return { ...next, sourceHealth: event.payload as StreamState["sourceHealth"] };
    case "session.status":
      return applySessionStatus(
        next,
        event.payload as SessionStatusPatch,
        event.emitted_at,
      );
    case "quality.update": {
      const quality = event.payload as StreamState["quality"];
      return {
        ...next,
        quality,
        qualityHistory: [...next.qualityHistory, quality]
          .filter((item): item is NonNullable<typeof item> => item !== null)
          .slice(-HISTORY_LIMIT),
      };
    }
    case "cycle.started": {
      const cycleId = String(event.payload.cycle_id ?? "");
      if (!cycleId) {
        return next;
      }
      const existing = next.council.cycles[cycleId];
      const cycle: CycleView = existing
        ? {
            ...existing,
            evidenceHash:
              String(event.payload.evidence_hash ?? "") || existing.evidenceHash,
            startedAt: event.emitted_at ?? existing.startedAt,
          }
        : {
            cycleId,
            evidenceHash: String(event.payload.evidence_hash ?? ""),
            startedAt: event.emitted_at,
            claims: [],
            challenges: [],
            rejections: [],
            result: null,
          };
      return {
        ...next,
        council: {
          ...next.council,
          cycles: { ...next.council.cycles, [cycleId]: cycle },
          order: next.council.order.includes(cycleId)
            ? next.council.order
            : [...next.council.order, cycleId],
          discussionUnavailable: false,
        },
      };
    }
    case "agent.claim": {
      const cycleId = String(event.payload.cycle_id ?? "");
      if (!cycleId) {
        return next;
      }
      const cycle = next.council.cycles[cycleId] ?? {
        cycleId,
        claims: [],
        challenges: [],
        rejections: [],
        result: null,
      };
      return {
        ...next,
        council: {
          ...next.council,
          cycles: {
            ...next.council.cycles,
            [cycleId]: {
              ...cycle,
              claims: (event.payload.claims as CycleView["claims"]) ?? cycle.claims,
              challenges:
                (event.payload.challenges as CycleView["challenges"]) ??
                cycle.challenges,
              rejections:
                (event.payload.rejections as CycleView["rejections"]) ??
                cycle.rejections,
            },
          },
          order: next.council.order.includes(cycleId)
            ? next.council.order
            : [...next.council.order, cycleId],
          discussionUnavailable: false,
        },
      };
    }
    case "agent.challenge":
    case "agent.response":
    case "policy.rejection":
      return next;
    case "synthesis.result": {
      const cycleId = String(event.payload.cycle_id ?? "");
      const result = event.payload.result as NonNullable<CycleView["result"]>;
      if (!result) {
        return next;
      }
      return applyResult(next, cycleId, result);
    }
    case "alert": {
      alertSeq += 1;
      const alert: AlertItem = {
        id: `alert-${alertSeq}`,
        level: (event.payload.level as AlertItem["level"]) ?? "info",
        message: String(event.payload.message ?? "未知告警"),
        emittedAt: event.emitted_at ?? new Date().toISOString(),
      };
      return { ...next, alerts: [...next.alerts, alert].slice(-12) };
    }
    case "heartbeat":
      return next;
    case "render.update":
      return next;
    default:
      return next;
  }
}

function applyTriplet(state: StreamState, triplet: SignalTriplet): StreamState {
  return {
    ...state,
    triplet,
    history: [...state.history, triplet].slice(-HISTORY_LIMIT),
  };
}

function applyResult(
  state: StreamState,
  cycleId: string,
  result: NonNullable<CycleView["result"]>,
): StreamState {
  const existing = state.council.cycles[cycleId];
  const cycle: CycleView = existing
    ? { ...existing, result }
    : {
        cycleId,
        evidenceHash: result.evidence_hash,
        claims: [],
        challenges: [],
        rejections: [],
        result,
      };
  return {
    ...state,
    council: {
      ...state.council,
      cycles: { ...state.council.cycles, [cycleId]: cycle },
      order: state.council.order.includes(cycleId)
        ? state.council.order
        : [...state.council.order, cycleId],
      discussionUnavailable: false,
    },
  };
}

export function streamReducer(state: StreamState, action: StreamAction): StreamState {
  switch (action.type) {
    case "event":
      return applyEvent(state, action.event);
    case "connection":
      return {
        ...state,
        connection: action.status,
        stale: action.status === "offline" ? true : state.stale,
      };
    case "settings":
      return { ...state, settings: { ...(state.settings ?? DEFAULT_SETTINGS), ...action.patch } };
    case "replay-bundles":
      return {
        ...state,
        replay: { ...state.replay, bundles: action.bundles, error: null },
      };
    case "replay-error":
      return { ...state, replay: { ...state.replay, error: action.error } };
    case "replay-select":
      return { ...state, replay: { ...state.replay, selected: action.bundleId } };
    case "replay-verifying":
      return { ...state, replay: { ...state.replay, verifying: action.bundleId } };
    case "reset":
      return initialState();
    default:
      return state;
  }
}

export interface StreamControls {
  pause: () => void;
  resume: () => void;
  step: (frames: number) => void;
  seek: (seconds: number) => void;
  rate: (rate: number) => void;
  record: () => void;
  start: (bundleId: string) => Promise<void>;
  stop: () => Promise<void>;
  loadBundles: () => Promise<void>;
  setSettings: (settings: Settings) => void;
}

/**
 * Turn an HTTP control response into the same event shape as the WebSocket.
 * The envelope session id is essential: a newly started session restarts its
 * sequence at one, so the reducer must clear the previous session's high-water
 * mark before the first real event arrives.
 */
function sessionStatusEvent(status: SessionStatus): StreamEvent {
  const sessionId =
    typeof status.session_id === "string" && status.session_id.length > 0
      ? status.session_id
      : undefined;
  return {
    session_id: sessionId,
    emitted_at: status.updated_at || undefined,
    event_type: "session.status",
    payload: status as unknown as Record<string, unknown>,
  };
}

interface StreamContextValue {
  state: StreamState;
  controls: StreamControls;
}

export const StreamContext = createContext<StreamContextValue | null>(null);

export function StreamProvider({ children }: { children: ReactNode }) {
  const [state, dispatch] = useReducer(streamReducer, undefined, initialState);
  const clientRef = useRef<StreamClient | null>(null);

  useEffect(() => {
    (window as unknown as { __wscState?: StreamState }).__wscState = state;
  }, [state]);

  useEffect(() => {
    const client = new StreamClient({
      url: wsUrl(),
      onEvent: (event) => dispatch({ type: "event", event }),
      onStatus: (status) => dispatch({ type: "connection", status }),
    });
    clientRef.current = client;
    client.connect();
    return () => {
      client.close();
      clientRef.current = null;
    };
  }, []);

  const controls = useMemo<StreamControls>(() => {
    const send = (action: string, payload?: Record<string, unknown>) =>
      clientRef.current?.control(action, payload);
    return {
      pause: () => send("pause"),
      resume: () => send("resume"),
      step: (frames: number) => send("step", { frames }),
      seek: (seconds: number) => send("seek", { seconds }),
      rate: (rate: number) => send("rate", { rate }),
      record: () => send("record"),
      start: async (bundleId: string) => {
        dispatch({ type: "replay-verifying", bundleId });
        try {
          const status = await startStream(bundleId);
          dispatch({
            type: "event",
            event: sessionStatusEvent(status),
          });
          dispatch({ type: "replay-select", bundleId });
        } catch (error) {
          dispatch({
            type: "replay-error",
            error: error instanceof Error ? error.message : String(error),
          });
        } finally {
          dispatch({ type: "replay-verifying", bundleId: null });
        }
      },
      stop: async () => {
        try {
          const status = await stopStream();
          dispatch({
            type: "event",
            event: sessionStatusEvent(status),
          });
        } catch (error) {
          dispatch({
            type: "replay-error",
            error: error instanceof Error ? error.message : String(error),
          });
        }
      },
      loadBundles: async () => {
        try {
          const bundles = await fetchBundles();
          dispatch({ type: "replay-bundles", bundles });
        } catch (error) {
          dispatch({
            type: "replay-error",
            error: error instanceof Error ? error.message : String(error),
          });
        }
      },
      setSettings: (settings: Settings) => dispatch({ type: "settings", patch: settings }),
    };
  }, []);

  useEffect(() => {
    void controls.loadBundles();
  }, [controls]);

  return (
    <StreamContext.Provider value={{ state, controls }}>
      {children}
    </StreamContext.Provider>
  );
}

export function useStream(): StreamContextValue {
  const value = useContext(StreamContext);
  if (!value) {
    throw new Error("useStream must be used inside StreamProvider");
  }
  return value;
}
