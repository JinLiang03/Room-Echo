import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { initialState, StreamContext, type StreamControls } from "../lib/state";
import { MemoryView } from "./MemoryView";

describe("MemoryView", () => {
  it("offers a one-click demo replay and returns to the live field", async () => {
    window.location.hash = "#/replay";
    window.localStorage.clear();
    const start = vi.fn(async () => undefined);
    const stop = vi.fn(async () => undefined);
    const controls = {
      start,
      pause: () => undefined,
      resume: () => undefined,
      step: () => undefined,
      seek: () => undefined,
      rate: () => undefined,
      record: () => undefined,
      stop,
      loadBundles: async () => undefined,
      setSettings: () => undefined,
    } satisfies StreamControls;

    const state = initialState();
    state.session = {
      session_id: "mock-running",
      mode: "mock",
      source_id: "demo_2min",
      bundle_id: null,
      running: true,
      finished: false,
      paused: false,
      rate: 1,
      position_s: 12,
      frames: 120,
      windows: 2,
      evidence_seals: 0,
      recording: false,
      recompute: true,
      updated_at: "2026-08-08T00:00:00Z",
    };

    render(
      <StreamContext.Provider value={{ state, controls }}>
        <MemoryView />
      </StreamContext.Provider>,
    );

    fireEvent.click(screen.getByRole("button", { name: "快速重播演示" }));
    await waitFor(() => expect(stop).toHaveBeenCalledTimes(1));
    await waitFor(() => expect(start).toHaveBeenCalledWith("demo_2min"));
    expect(stop.mock.invocationCallOrder[0]).toBeLessThan(
      start.mock.invocationCallOrder[0],
    );
    expect(window.location.hash).toBe("#/home");
  });
});
