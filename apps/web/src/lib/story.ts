import {
  agentChallenges,
  agentClaims,
  councilCycleDetails,
  councilResults,
  policyRejections,
  signalTriplets,
} from "../generated/fixtures";
import type {
  AgentChallenge,
  AgentClaim,
  CouncilResult,
  PolicyRejection,
  SignalTriplet,
  StreamState,
} from "./types";
import { DEFAULT_SETTINGS, initialState } from "./state";

export type StoryScenario =
  | "idle"
  | "moving"
  | "interference"
  | "single_rx"
  | "unknown"
  | "ambiguous"
  | "timeout"
  | "rejected";

export const STORY_SCENARIOS: StoryScenario[] = [
  "idle",
  "moving",
  "interference",
  "single_rx",
  "unknown",
  "ambiguous",
  "timeout",
  "rejected",
];

function tripletAt(index: number): SignalTriplet {
  return signalTriplets[index] as SignalTriplet;
}

function cycleFromFixture(
  resultIndex: number,
  opts?: {
    claims?: AgentClaim[];
    challenges?: AgentChallenge[];
    rejections?: PolicyRejection[];
    result?: CouncilResult;
  },
): NonNullable<StreamState["council"]["cycles"][string]> {
  const fixture = councilCycleDetails[resultIndex] as {
    cycle_id: string;
    evidence_hash: string;
    claims?: AgentClaim[];
    challenges?: AgentChallenge[];
    rejections?: PolicyRejection[];
    result: CouncilResult;
  };
  return {
    cycleId: fixture.cycle_id,
    evidenceHash: fixture.evidence_hash,
    startedAt: "2026-08-06T12:00:00Z",
    claims: opts?.claims ?? fixture.claims ?? [],
    challenges: opts?.challenges ?? fixture.challenges ?? [],
    rejections: opts?.rejections ?? fixture.rejections ?? [],
    result:
      opts?.result ??
      (opts ? fixture.result : (councilResults[resultIndex] as CouncilResult)),
  };
}

function withCycle(
  base: StreamState,
  cycle: NonNullable<StreamState["council"]["cycles"][string]>,
): StreamState {
  return {
    ...base,
    council: {
      cycles: { [cycle.cycleId]: cycle },
      order: [cycle.cycleId],
      discussionUnavailable: false,
    },
  };
}

function base(triplet: SignalTriplet): StreamState {
  const state = initialState();
  return {
    ...state,
    connection: "online",
    sequence: 100,
    applied: 100,
    triplet,
    history: Array.from({ length: 40 }, (_, index) => ({
      ...triplet,
      window_id: `story-${index}`,
    })),
    sourceHealth: {
      source_mode: "mock",
      link_ids: ["rx-a", "rx-b"],
      topology_hash: "sha256:story-topology",
      calibration_profile_id: "demo_room_v1",
      channel: 6,
      bandwidth_mhz: 20,
      recompute: false,
    },
    session: {
      bundle_id: "story",
      running: true,
      finished: false,
      paused: false,
      rate: 1,
      position_s: 8.2,
      frames: 1640,
      windows: 33,
      evidence_seals: 3,
      recording: false,
      recompute: false,
      updated_at: "2026-08-06T12:00:00Z",
    },
    quality: {
      window_id: triplet.window_id,
      status: triplet.status,
      packet_coverage: 0.98,
      paired_coverage: 0.95,
      link_health: { "rx-a": "ok", "rx-b": "ok" },
      quality_flags:
        triplet.status === "degraded" ? ["degraded"] : [],
    },
    qualityHistory: [],
    settings: DEFAULT_SETTINGS,
    lastEventAt: Date.now(),
  };
}

export function buildStoryState(scenario: StoryScenario): StreamState {
  switch (scenario) {
    case "idle": {
      const state = base(tripletAt(0));
      return { ...state, council: initialState().council };
    }
    case "moving": {
      const state = base(tripletAt(1));
      return withCycle(state, cycleFromFixture(0));
    }
    case "interference": {
      const triplet: SignalTriplet = {
        ...tripletAt(1),
        status: "degraded",
      };
      const state = base(triplet);
      const challenge = agentChallenges[0] as AgentChallenge;
      const claim = agentClaims[0] as AgentClaim;
      return withCycle(
        state,
        cycleFromFixture(0, {
          claims: [claim],
          challenges: [
            {
              ...challenge,
              status: "open",
              proposed_severity: "material",
              statement: "运动扰动可能由无线干扰注入产生,而非实体运动.",
            },
          ],
        }),
      );
    }
    case "single_rx": {
      const triplet: SignalTriplet = {
        ...tripletAt(1),
        occupancy_density: {
          probabilities: { low: 0, medium: 0, high: 0, unknown: 1 },
          state: "unknown",
          confidence: 0,
        },
        depth_zone: {
          probabilities: { near: 0, mid: 0, far: 0, unknown: 1 },
          state: "unknown",
          confidence: 0,
        },
        sensor_confidence_cap: 0,
        status: "insufficient_signal",
      };
      const state = base(triplet);
      return {
        ...state,
        sourceHealth: { ...state.sourceHealth, link_ids: ["rx-a"] },
        council: initialState().council,
      };
    }
    case "unknown": {
      const state = base(tripletAt(2));
      return {
        ...state,
        council: {
          cycles: {},
          order: [],
          discussionUnavailable: true,
        },
      };
    }
    case "ambiguous": {
      const state = base(tripletAt(1));
      const result = councilResults[0] as CouncilResult;
      const ambiguous: CouncilResult = {
        ...result,
        status: "ambiguous",
        headline: "证据解读存在未解决质疑",
        summary: "存在未解决挑战:challenge-story-01.",
        display_confidence: 0.5 * result.model_support,
        interpretation_agreement: {
          ...result.interpretation_agreement,
          unresolved_challenges: 1,
        },
      };
      const challenge = agentChallenges[0] as AgentChallenge;
      return withCycle(
        state,
        cycleFromFixture(0, {
          challenges: [{ ...challenge, status: "open" }],
          rejections: [],
          result: ambiguous,
        }),
      );
    }
    case "timeout": {
      const state = base(tripletAt(1));
      return {
        ...state,
        council: { cycles: {}, order: [], discussionUnavailable: true },
        alerts: [
          {
            id: "story-timeout",
            level: "warn",
            message: "Council 周期超过硬性时限;保留确定性传感器摘要.",
            emittedAt: "2026-08-06T12:00:00Z",
          },
        ],
      };
    }
    case "rejected": {
      const state = base(tripletAt(1));
      const claim = agentClaims[0] as AgentClaim;
      const rejectedClaim: AgentClaim = {
        ...claim,
        claim_id: "claim-story-rejected",
        proposition: "墙后有人,能看出一个人.",
        state: "withdrawn",
      };
      const rejection = policyRejections[0] as PolicyRejection;
      return withCycle(
        state,
        cycleFromFixture(0, {
          claims: [rejectedClaim],
          rejections: [
            {
              ...rejection,
              target_id: rejectedClaim.claim_id,
              reason_code: "forbidden_wall_presence",
              detail: "越权主张:墙后存在被拒绝.",
            },
          ],
        }),
      );
    }
  }
}
