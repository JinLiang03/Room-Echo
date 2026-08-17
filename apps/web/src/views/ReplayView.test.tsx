import { describe, expect, it } from "vitest";
import { ReplayView } from "./ReplayView";
import { renderWithStream } from "../test-utils";
import { initialState } from "../lib/state";
import type { StreamState } from "../lib/types";

function stateWithBundles(): StreamState {
  const state = initialState();
  return {
    ...state,
    replay: {
      ...state.replay,
      bundles: [
        {
          bundle_id: "walk_through",
          verified: true,
          raw_bytes: 356_000,
          manifest: {
            recording_id: "walk_through",
            session_id: "session-1",
            created_at: "2026-08-06T12:00:00Z",
            source_mode: "mock",
            topology_hash: "sha256:topo",
            calibration_profile_id: "demo_room_v1",
            channel: 6,
            bandwidth_mhz: 20,
            ground_truth_present: true,
            privacy: "mock fixture",
            status: "complete",
          },
          errors: [],
        },
        {
          bundle_id: "broken",
          verified: false,
          raw_bytes: 0,
          manifest: null,
          errors: ["checksum mismatch"],
        },
      ],
      selected: "walk_through",
    },
  };
}

describe("ReplayView", () => {
  it("lists verified and failed bundles; failed shows reason", () => {
    const { getByText } = renderWithStream(<ReplayView />, stateWithBundles());
    expect(getByText("walk_through")).toBeDefined();
    expect(getByText("verify failed")).toBeDefined();
    expect(getByText("checksum mismatch")).toBeDefined();
  });

  it("hides ground truth by default and labels it", () => {
    const { getByText } = renderWithStream(<ReplayView />, stateWithBundles());
    expect(getByText(/ground truth 已隐藏/)).toBeDefined();
  });

  it("shows ground truth only in evaluation mode", () => {
    const state = stateWithBundles();
    state.settings = { ...state.settings, showGroundTruth: true };
    const { getByText } = renderWithStream(<ReplayView />, state);
    expect(getByText(/评估模式/)).toBeDefined();
    expect(getByText(/不进入 Agent/)).toBeDefined();
  });
});
