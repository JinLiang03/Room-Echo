import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { initialState, StreamContext, type StreamControls } from "../lib/state";
import { TopBar } from "./TopBar";

const controls = {
  pause: () => undefined,
  resume: () => undefined,
  step: () => undefined,
  seek: () => undefined,
  rate: () => undefined,
  record: () => undefined,
  start: async () => undefined,
  stop: async () => undefined,
  loadBundles: async () => undefined,
  setSettings: () => undefined,
} satisfies StreamControls;

function renderTopBar(mode?: string) {
  const state = initialState();
  state.sourceHealth = mode ? { source_mode: mode } : null;
  return render(
    <StreamContext.Provider value={{ state, controls }}>
      <TopBar route="home" onNavigate={vi.fn()} />
    </StreamContext.Provider>,
  );
}

describe("TopBar source truth badge", () => {
  it("marks mock and replay as simulated, non-live sources", () => {
    const mock = renderTopBar("mock");
    expect(screen.getByText("SIM · MOCK")).toBeDefined();
    expect(screen.getByLabelText(/模拟数据，非实时硬件/)).toBeDefined();
    mock.unmount();

    renderTopBar("replay");
    expect(screen.getByText("SIM · REPLAY")).toBeDefined();
    expect(screen.getByLabelText(/回放数据，非实时硬件/)).toBeDefined();
  });

  it("uses LIVE only for the live source mode", () => {
    renderTopBar("live");
    expect(screen.getByText("LIVE")).toBeDefined();
    expect(screen.getByLabelText(/LIVE 实时硬件/)).toBeDefined();
    expect(screen.queryByText(/SIM ·/)).toBeNull();
  });

  it("fails closed while the source mode is unknown", () => {
    renderTopBar();
    expect(screen.getByText("SIM · WAIT")).toBeDefined();
    expect(screen.getByLabelText(/尚未确认，非实时硬件/)).toBeDefined();
  });
});
