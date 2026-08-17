import { describe, expect, it } from "vitest";
import { initialState, streamReducer } from "./state";
import type { SessionStatus, SignalTriplet, StreamEvent } from "./types";
import { signalTriplets } from "../generated/fixtures";

function event(
  sequence: number,
  eventType: StreamEvent["event_type"],
  payload: Record<string, unknown>,
): StreamEvent {
  return {
    schema_version: "ws-event.v1",
    session_id: "session-test",
    sequence,
    emitted_at: "2026-08-06T12:00:00Z",
    event_type: eventType,
    payload,
  };
}

function apply(state: ReturnType<typeof initialState>, ev: StreamEvent) {
  return streamReducer(state, { type: "event", event: ev });
}

const triplet = signalTriplets[1] as SignalTriplet;

describe("streamReducer", () => {
  it("applies signal.frame and keeps bounded history", () => {
    let state = initialState();
    for (let seq = 1; seq <= 5; seq += 1) {
      state = apply(
        state,
        event(seq, "signal.frame", { triplet: { ...triplet, window_id: `w-${seq}` } }),
      );
    }
    expect(state.sequence).toBe(5);
    expect(state.applied).toBe(5);
    expect(state.history).toHaveLength(5);
    expect(state.triplet?.window_id).toBe("w-5");
  });

  it("drops out-of-order and duplicate events", () => {
    let state = initialState();
    state = apply(state, event(10, "signal.frame", { triplet }));
    state = apply(state, event(10, "signal.frame", { triplet }));
    state = apply(state, event(8, "signal.frame", { triplet }));
    expect(state.dropped).toBe(2);
    expect(state.applied).toBe(1);
    expect(state.sequence).toBe(10);
  });

  it("accepts a restarted session even when its sequence restarts at one", () => {
    let state = apply(
      initialState(),
      {
        ...event(20, "session.status", {
          session_id: "session-old",
          running: true,
          finished: false,
          paused: false,
          rate: 1,
          position_s: 10,
          frames: 100,
          windows: 10,
          evidence_seals: 1,
          recording: false,
          recompute: true,
          updated_at: "2026-08-06T12:00:00Z",
        }),
        session_id: "session-old",
      },
    );
    state = apply(
      state,
      { ...event(21, "signal.frame", { triplet }), session_id: "session-old" },
    );
    state = apply(
      state,
      {
        ...event(1, "session.status", {
          session_id: "session-new",
          running: true,
          finished: false,
          paused: false,
          rate: 1,
          position_s: 0,
          frames: 0,
          windows: 0,
          evidence_seals: 0,
          recording: false,
          recompute: true,
          updated_at: "2026-08-06T12:01:00Z",
        }),
        session_id: "session-new",
      },
    );
    expect(state.session?.session_id).toBe("session-new");
    expect(state.sequence).toBe(1);
    expect(state.history).toEqual([]);
    expect(state.dropped).toBe(0);
  });

  it("resets the sequence high-water mark from a start control response", () => {
    let state = apply(
      initialState(),
      {
        ...event(91, "session.status", {
          session_id: "session-old",
          mode: "replay",
          running: true,
          finished: false,
          paused: false,
          rate: 1,
          position_s: 30,
          frames: 300,
          windows: 30,
          evidence_seals: 3,
          recording: false,
          recompute: true,
          updated_at: "2026-08-06T12:00:00Z",
        }),
        session_id: "session-old",
      },
    );
    state = apply(
      state,
      { ...event(92, "signal.frame", { triplet }), session_id: "session-old" },
    );

    const started: SessionStatus = {
      session_id: "session-new",
      mode: "replay",
      source_id: "demo_2min",
      bundle_id: "demo_2min",
      running: true,
      finished: false,
      paused: false,
      rate: 1,
      position_s: 0,
      frames: 0,
      windows: 0,
      evidence_seals: 0,
      recording: false,
      recompute: true,
      updated_at: "2026-08-06T12:01:00Z",
    };
    const synthetic: StreamEvent = {
      session_id: started.session_id ?? undefined,
      emitted_at: started.updated_at,
      event_type: "session.status",
      payload: started as unknown as Record<string, unknown>,
    };
    expect(synthetic.session_id).toBe("session-new");
    state = apply(state, synthetic);

    expect(state.session?.session_id).toBe("session-new");
    expect(state.sequence).toBe(-1);
    expect(state.history).toEqual([]);

    state = apply(
      state,
      { ...event(1, "signal.frame", { triplet }), session_id: "session-new" },
    );
    expect(state.sequence).toBe(1);
    expect(state.triplet?.window_id).toBe(triplet.window_id);
    expect(state.dropped).toBe(0);
  });

  it("applies snapshot with catch-up without dropping buffered events", () => {
    let state = initialState();
    state = apply(
      state,
      event(1, "snapshot", {
        status: {
          running: true,
          finished: false,
          paused: false,
          rate: 1,
          position_s: 1,
          frames: 100,
          windows: 10,
          evidence_seals: 1,
          recording: false,
          recompute: false,
          updated_at: "2026-08-06T12:00:00Z",
        },
        latest_triplet: triplet,
        latest_result: null,
        catch_up: [
          event(2, "signal.frame", { triplet: { ...triplet, window_id: "w-2" } }),
          event(3, "signal.frame", { triplet: { ...triplet, window_id: "w-3" } }),
        ],
      }),
    );
    expect(state.dropped).toBe(0);
    expect(state.sequence).toBe(3);
    expect(state.applied).toBe(2);
    expect(state.triplet?.window_id).toBe("w-3");
    expect(state.session?.running).toBe(true);
  });

  it("hydrates recent events into source, signal history, and a complete council cycle", () => {
    const result = {
      schema_version: "council-result.v1",
      cycle_id: "cycle-restored",
      evidence_hash: "sha256:restored",
      status: "ambiguous",
      headline: "恢复后的受限解读",
      summary: "恢复摘要",
      sensor_confidence_cap: 0.7,
      model_support: 0.6,
      display_confidence: 0.6,
      interpretation_agreement: {
        participants: 2,
        supporting: 1,
        contradicting: 1,
        unresolved_challenges: 1,
        agreement_ratio: 0.5,
      },
      provenance: {
        contracts_version: "1.0.0",
        features_version: "features-v2",
        calibration_profile_id: "demo_room_v1",
        policy_version: "policy-v1",
        generated_at: "2026-08-06T12:00:00Z",
      },
    };
    const recent = [
      event(1, "source.health", {
        source_mode: "replay",
        link_ids: ["rx-a", "rx-b"],
        calibration_profile_id: "demo_room_v1",
      }),
      event(2, "signal.frame", { triplet }),
      event(3, "cycle.started", {
        cycle_id: "cycle-restored",
        evidence_hash: "sha256:restored",
      }),
      event(4, "agent.claim", {
        cycle_id: "cycle-restored",
        claims: [{ claim_id: "claim-restored" }],
        challenges: [{ challenge_id: "challenge-restored" }],
        rejections: [{ rejection_id: "rejection-restored" }],
      }),
      event(5, "synthesis.result", {
        cycle_id: "cycle-restored",
        result,
      }),
    ];

    const state = apply(
      initialState(),
      event(6, "snapshot", {
        status: {
          session_id: "session-test",
          mode: "replay",
          source_id: "demo_2min",
          bundle_id: "demo_2min",
          running: true,
          finished: false,
          paused: false,
          rate: 1,
          position_s: 30,
          frames: 6000,
          windows: 112,
          evidence_seals: 2,
          recording: false,
          recompute: true,
          updated_at: "2026-08-06T12:00:00Z",
        },
        latest_source_health: {
          source_mode: "replay",
          link_ids: ["rx-a", "rx-b"],
          calibration_profile_id: "demo_room_v1",
          channel: 6,
        },
        latest_triplet: triplet,
        latest_result: result,
        recent_events: recent,
        catch_up: [recent[4]],
      }),
    );

    expect(state.sequence).toBe(6);
    expect(state.dropped).toBe(0);
    expect(state.sourceHealth?.channel).toBe(6);
    expect(state.history).toHaveLength(1);
    expect(state.triplet?.window_id).toBe(triplet.window_id);
    expect(state.council.order).toEqual(["cycle-restored"]);
    expect(state.council.cycles["cycle-restored"].claims).toHaveLength(1);
    expect(state.council.cycles["cycle-restored"].challenges).toHaveLength(1);
    expect(state.council.cycles["cycle-restored"].rejections).toHaveLength(1);
    expect(state.council.cycles["cycle-restored"].result?.status).toBe(
      "ambiguous",
    );
  });

  it("merges partial session status updates without erasing known fields", () => {
    let state = apply(
      initialState(),
      event(1, "session.status", {
        session_id: "session-test",
        mode: "replay",
        source_id: "demo_2min",
        bundle_id: "demo_2min",
        running: true,
        finished: false,
        paused: false,
        rate: 2,
        position_s: 20,
        frames: 4000,
        windows: 72,
        evidence_seals: 2,
        recording: false,
        recompute: true,
        updated_at: "2026-08-06T12:00:00Z",
      }),
    );
    state = apply(state, event(2, "session.status", { recording: true }));
    expect(state.session).toMatchObject({
      session_id: "session-test",
      source_id: "demo_2min",
      running: true,
      rate: 2,
      position_s: 20,
      recording: true,
    });
    expect(state.stale).toBe(false);

    state = apply(
      state,
      event(3, "session.status", { state: "finished", frames: 4100 }),
    );
    expect(state.session).toMatchObject({
      session_id: "session-test",
      source_id: "demo_2min",
      running: false,
      finished: true,
      frames: 4100,
      windows: 72,
    });
    expect(state.stale).toBe(true);
  });

  it("clears derived timeline state when a seek revision changes", () => {
    let state = apply(
      initialState(),
      event(1, "session.status", {
        session_id: "session-test",
        running: true,
        finished: false,
        paused: false,
        timeline_revision: 0,
        rate: 1,
        position_s: 20,
        frames: 4000,
        windows: 72,
        evidence_seals: 2,
        recording: false,
        recompute: true,
        updated_at: "2026-08-06T12:00:00Z",
      }),
    );
    state = apply(state, event(2, "signal.frame", { triplet }));
    state = apply(
      state,
      event(3, "cycle.started", {
        cycle_id: "cycle-before-seek",
        evidence_hash: "sha256:before",
      }),
    );

    state = apply(
      state,
      event(4, "session.status", {
        timeline_revision: 1,
        position_s: 0,
        paused: true,
      }),
    );
    expect(state.session?.session_id).toBe("session-test");
    expect(state.session?.timeline_revision).toBe(1);
    expect(state.triplet).toBeNull();
    expect(state.history).toEqual([]);
    expect(state.council.order).toEqual([]);
    expect(state.stale).toBe(true);
  });

  it("marks stale on pause and finished session status", () => {
    let state = initialState();
    state = apply(
      state,
      event(1, "session.status", {
        running: true,
        finished: false,
        paused: true,
        rate: 1,
        position_s: 2,
        frames: 10,
        windows: 1,
        evidence_seals: 0,
        recording: false,
        recompute: false,
        updated_at: "2026-08-06T12:00:00Z",
      }),
    );
    expect(state.stale).toBe(true);
    state = apply(
      state,
      event(2, "session.status", {
        running: false,
        finished: true,
        paused: false,
        rate: 1,
        position_s: 10,
        frames: 10,
        windows: 1,
        evidence_seals: 0,
        recording: false,
        recompute: false,
        updated_at: "2026-08-06T12:00:00Z",
      }),
    );
    expect(state.stale).toBe(true);
  });

  it("builds a council cycle from cycle.started, agent.claim, synthesis.result", () => {
    let state = initialState();
    state = apply(
      state,
      event(1, "cycle.started", {
        cycle_id: "cycle-0001",
        evidence_hash: "sha256:abcd",
      }),
    );
    state = apply(
      state,
      event(2, "agent.claim", {
        cycle_id: "cycle-0001",
        claims: [],
        challenges: [],
        rejections: [],
      }),
    );
    state = apply(
      state,
      event(3, "synthesis.result", {
        cycle_id: "cycle-0001",
        result: {
          schema_version: "council-result.v1",
          cycle_id: "cycle-0001",
          evidence_hash: "sha256:abcd",
          status: "supported",
          headline: "代理信号的受限解读",
          summary: "摘要",
          sensor_confidence_cap: 0.8,
          model_support: 0.8,
          display_confidence: 0.8,
          interpretation_agreement: {
            participants: 4,
            supporting: 4,
            contradicting: 0,
            unresolved_challenges: 0,
            agreement_ratio: 1,
          },
          provenance: {
            contracts_version: "1.0.0",
            features_version: "features-v2",
            calibration_profile_id: "demo_room_v1",
            policy_version: "policy-v1",
            generated_at: "2026-08-06T12:00:00Z",
          },
        },
      }),
    );
    expect(state.council.order).toEqual(["cycle-0001"]);
    expect(state.council.discussionUnavailable).toBe(false);
    expect(state.council.cycles["cycle-0001"]?.result?.status).toBe("supported");
  });

  it("appends alerts up to a bound", () => {
    let state = initialState();
    for (let seq = 1; seq <= 15; seq += 1) {
      state = apply(
        state,
        event(seq, "alert", { level: "warn", message: `m-${seq}` }),
      );
    }
    expect(state.alerts.length).toBe(12);
    expect(state.alerts[state.alerts.length - 1].message).toBe("m-15");
  });
});
