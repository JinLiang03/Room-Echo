import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { initialState, StreamContext, type StreamControls } from "../lib/state";
import { MemoryView } from "./MemoryView";

describe("MemoryView", () => {
  it("keeps care scenario data out of the public memory surface", () => {
    const state = initialState();
    render(
      <StreamContext.Provider value={{ state, controls: baseControls() }}>
        <MemoryView />
      </StreamContext.Provider>,
    );

    expect(screen.getByText("本机视觉书签 · 非场景识别")).toBeDefined();
    expect(screen.getByLabelText("还没有保存的本机视觉记忆")).toBeDefined();
    expect(document.querySelector(".room-echo-page-lead")).toBeNull();
    expect(document.querySelector(".care-day-memory")).toBeNull();
    expect(document.querySelector(".care-scenario-selector")).toBeNull();
  });

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

  it("returns to the supervisor-owned public replay without sending mutations", () => {
    window.location.hash = "#/memory";
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
      session_id: "public-replay",
      read_only: true,
      mode: "replay",
      source_id: "demo_2min",
      bundle_id: "demo_2min",
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
      updated_at: "2026-08-09T00:00:00Z",
    };

    render(
      <StreamContext.Provider value={{ state, controls }}>
        <MemoryView />
      </StreamContext.Provider>,
    );

    fireEvent.click(screen.getByRole("button", { name: "返回当前回放" }));
    expect(start).not.toHaveBeenCalled();
    expect(stop).not.toHaveBeenCalled();
    expect(window.location.hash).toBe("#/home");
  });
});

function baseControls(): StreamControls {
  return {
    start: async () => undefined,
    pause: () => undefined,
    resume: () => undefined,
    step: () => undefined,
    seek: () => undefined,
    rate: () => undefined,
    record: () => undefined,
    stop: async () => undefined,
    loadBundles: async () => undefined,
    setSettings: () => undefined,
  };
}
