import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import App from "./App";

vi.mock("./lib/ws", () => ({
  StreamClient: class {
    connect(): void {}
    close(): void {}
    control(): void {}
  },
}));

vi.mock("./lib/api", () => ({
  // These shell tests do not exercise the replay catalog. Keep the request
  // pending so it cannot schedule an unrelated provider update after render.
  fetchBundles: () => new Promise(() => undefined),
  startStream: async () => ({}),
  stopStream: async () => ({}),
  wsUrl: () => "ws://test/ws",
}));

describe("App shell", () => {
  beforeEach(() => {
    window.location.hash = "";
    window.localStorage.clear();
  });

  it("renders the digit inference-field home by default", () => {
    render(<App />);
    const lifeStateStrip = screen.getByRole("group", {
      name: /七种数字生命状态的视觉谱系/,
    });
    expect(lifeStateStrip.querySelectorAll(".life-state-strip-body")).toHaveLength(7);
    expect(lifeStateStrip.textContent).toBe("");
    expect(screen.queryByText(/NOT A CAMERA IMAGE/)).toBeNull();
    expect(screen.queryByText(/measured 测量/)).toBeNull();
    expect(screen.getByRole("button", { name: "此刻" })).toBeDefined();
    expect(screen.getByRole("button", { name: "记忆" })).toBeDefined();
    expect(screen.getByRole("button", { name: "为什么" })).toBeDefined();
    expect(screen.getByRole("button", { name: "设置" })).toBeDefined();
    expect(screen.queryByRole("button", { name: "Observe" })).toBeNull();
    expect(screen.queryByRole("button", { name: "Story" })).toBeNull();
    expect(screen.queryByRole("radiogroup", { name: "选择数字场视觉主题" })).toBeNull();
    expect(screen.getByLabelText("七个 Agent 实时观点")).toBeDefined();
    expect(screen.queryByText("同一个数字生命的七种读法")).toBeNull();
    expect(document.querySelectorAll(".agent-voice-content")).toHaveLength(6);
    expect(document.querySelectorAll(".agent-sound-motion")).toHaveLength(1);
    expect(document.querySelectorAll(".voice-digit-canvas")).toHaveLength(0);
    expect(screen.getByText("ARCHITECTURE")).toBeDefined();
    expect(screen.queryByText("筑间")).toBeNull();
    expect(screen.getByLabelText("此刻的数字生命")).toBeDefined();
  });

  it("does not fabricate a memory while evidence is unavailable", () => {
    render(<App />);
    expect(screen.getByLabelText(/证据不足，身体未完全成形/)).toBeDefined();
    expect(screen.queryByRole("button", { name: /保存这一刻/ })).toBeNull();
    expect(window.localStorage.length).toBe(0);
    expect(window.location.hash).toBe("");
  });

  it("navigates to story route and shows scenario picker", async () => {
    window.location.hash = "/story";
    render(<App />);
    expect(await screen.findByText(/固定状态演示/)).toBeDefined();
    expect(await screen.findByRole("group", { name: "选择场景" })).toBeDefined();
    expect(screen.queryByText(/连接已断开/)).toBeNull();
    expect(screen.queryByRole("button", { name: "Start" })).toBeNull();
  });

  it("toggles settings and applies reduced-motion class", async () => {
    render(<App />);
    fireEvent.click(screen.getByRole("button", { name: "设置" }));
    const toggle = await screen.findByRole("checkbox", { name: /减少动态/ });
    fireEvent.click(toggle);
    expect(document.documentElement.classList.contains("reduced-motion")).toBe(true);
  });
});
