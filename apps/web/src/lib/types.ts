import type {
  AgentChallenge,
  AgentClaim,
  CouncilResult,
  PolicyRejection,
  SignalTriplet,
} from "../generated/contracts";

export type { AgentChallenge, AgentClaim, CouncilResult, PolicyRejection, SignalTriplet };

export type WsEventType =
  | "session.status"
  | "source.health"
  | "signal.frame"
  | "quality.update"
  | "cycle.started"
  | "agent.claim"
  | "agent.challenge"
  | "agent.response"
  | "policy.rejection"
  | "synthesis.result"
  | "render.update"
  | "alert"
  | "heartbeat"
  | "snapshot";

export interface StreamEvent {
  schema_version?: string;
  session_id?: string;
  sequence?: number;
  emitted_at?: string;
  event_type: WsEventType;
  payload: Record<string, unknown>;
}

export interface SessionStatus {
  schema_version?: string;
  state?: string;
  timeline_revision?: number;
  session_id?: string | null;
  read_only?: boolean;
  mode?: string | null;
  source_id?: string | null;
  bundle_id?: string | null;
  running: boolean;
  finished: boolean;
  paused: boolean;
  rate: number;
  position_s: number;
  demo_phase?: string | null;
  frames: number;
  windows: number;
  evidence_seals: number;
  recording: boolean;
  recompute: boolean;
  faults?: Record<string, Record<string, unknown>>;
  error?: string | null;
  ground_truth_present?: boolean;
  updated_at: string;
}

export interface SourceHealthView {
  source_mode?: string;
  link_ids?: string[];
  topology_hash?: string;
  calibration_profile_id?: string;
  calibration_simulated?: boolean;
  calibration_source?: string;
  calibration_state?: string;
  channel?: number;
  bandwidth_mhz?: number;
  recompute?: boolean;
}

export interface QualityView {
  window_id?: string;
  status?: string;
  packet_coverage?: number;
  paired_coverage?: number;
  link_health?: Record<string, string>;
  quality_flags?: string[];
}

export interface CycleView {
  cycleId: string;
  evidenceHash?: string;
  startedAt?: string;
  analysisRefreshS?: number;
  /** SignalTriplet captured when this EvidencePacket cycle was sealed. */
  signalSnapshot?: SignalTriplet;
  claims: AgentClaim[];
  challenges: AgentChallenge[];
  rejections: PolicyRejection[];
  result: CouncilResult | null;
}

export interface AlertItem {
  id: string;
  level: "info" | "warn" | "error";
  message: string;
  emittedAt: string;
}

export interface Settings {
  muted: boolean;
  reducedMotion: boolean;
  highContrast: boolean;
  debug: boolean;
  showGroundTruth: boolean;
}

export interface StreamState {
  connection: "connecting" | "online" | "offline";
  sequence: number;
  applied: number;
  dropped: number;
  session: SessionStatus | null;
  sourceHealth: SourceHealthView | null;
  triplet: SignalTriplet | null;
  history: SignalTriplet[];
  quality: QualityView | null;
  qualityHistory: QualityView[];
  council: {
    cycles: Record<string, CycleView>;
    order: string[];
    discussionUnavailable: boolean;
  };
  alerts: AlertItem[];
  replay: {
    bundles: ReplayBundleSummary[];
    selected: string | null;
    verifying: string | null;
    error: string | null;
    groundTruthHidden: boolean;
  };
  settings: Settings;
  stale: boolean;
  lastEventAt: number | null;
}

export interface ReplayBundleSummary {
  bundle_id: string;
  verified: boolean;
  raw_bytes: number;
  manifest?: {
    recording_id: string;
    session_id: string;
    created_at: string;
    source_mode: string;
    topology_hash: string;
    calibration_profile_id?: string | null;
    channel: number;
    bandwidth_mhz: number;
    ground_truth_present: boolean;
    privacy: string;
    status: string;
  } | null;
  errors: string[];
}

export const HISTORY_LIMIT = 240;
