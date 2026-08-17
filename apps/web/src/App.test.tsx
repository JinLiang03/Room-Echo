import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { simulatedCareScenarios } from "./generated/fixtures";
import App from "./App";

const apiMocks = vi.hoisted(() => ({
  fetchCareScenario: vi.fn(),
}));

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
  fetchCareScenario: apiMocks.fetchCareScenario,
  startStream: async () => ({}),
  stopStream: async () => ({}),
  wsUrl: () => "ws://test/ws",
}));

describe("App shell", () => {
  beforeEach(() => {
    window.location.hash = "";
    window.localStorage.clear();
    apiMocks.fetchCareScenario.mockReset();
    apiMocks.fetchCareScenario.mockResolvedValue(simulatedCareScenarios[0]);
  });

  it("renders the fail-closed care inference-field home by default", () => {
    apiMocks.fetchCareScenario.mockReturnValueOnce(new Promise(() => undefined));
    render(<App />);
    expect(screen.queryByRole("group", {
      name: /七种数字生命状态的视觉谱系/,
    })).toBeNull();
    expect(screen.getByText(/INFERENCE FIELD — NOT A CAMERA IMAGE/)).toBeDefined();
    expect(screen.queryByText(/measured 测量/)).toBeNull();
    expect(screen.getByRole("button", { name: "此刻" })).toBeDefined();
    expect(screen.getByRole("button", { name: "记忆" })).toBeDefined();
    expect(screen.getByRole("button", { name: "为什么" })).toBeDefined();
    expect(screen.queryByRole("button", { name: "设置" })).toBeNull();
    expect(screen.queryByRole("button", { name: "Observe" })).toBeNull();
    expect(screen.queryByRole("button", { name: "Story" })).toBeNull();
    expect(screen.queryByRole("radiogroup", { name: "选择数字场视觉主题" })).toBeNull();
    expect(screen.getByLabelText("Room Echo Agent 的模拟照护解释")).toBeDefined();
    expect(screen.getByLabelText("Room Echo Agent 的四项行动建议")).toBeDefined();
    expect(document.querySelectorAll(".action-suggestion")).toHaveLength(4);
    expect(screen.queryByLabelText("七个 Agent 实时观点")).toBeNull();
    expect(document.querySelectorAll('[data-public-agent="room-echo"]')).toHaveLength(1);
    expect(document.querySelectorAll(".agent-voice-content")).toHaveLength(0);
    expect(document.querySelectorAll(".voice-digit-canvas")).toHaveLength(0);
    expect(document.querySelector(".care-scenario-selector")).toBeNull();
    expect(document.querySelector(".room-echo-context")).toBeNull();
    expect(document.querySelector(".room-agent-status")?.children).toHaveLength(2);
    expect(document.querySelector(".room-agent-confidence")).toBeNull();
    expect(document.querySelector('[data-care-simulation="true"]')).not.toBeNull();
    expect(document.querySelectorAll('[data-action-source="care_workflow"]')).toHaveLength(4);
    expect(document.querySelectorAll('[data-action-status="withheld"]')).toHaveLength(4);
    expect(apiMocks.fetchCareScenario).toHaveBeenCalledTimes(1);
    expect(screen.getByText("SIM · CARE · WAITING")).toBeDefined();
    expect(screen.getByLabelText(/证据不足，身体未完全成形/)).toBeDefined();
    expect(document.querySelector(".digit-field")?.getAttribute("data-show-perimeter"))
      .toBe("false");
  });

  it("uses an explicit care parameter as the first frame without a separate page", async () => {
    window.location.hash = "/home?care=bathroom_timeout";
    render(<App />);

    expect(await screen.findByLabelText("Room Echo Agent 的模拟照护解释")).toBeDefined();
    expect(apiMocks.fetchCareScenario).toHaveBeenCalledTimes(1);
    expect(screen.getByText("SIM · CARE")).toBeDefined();
  });

  it("falls an invalid care parameter back to the routine frame", async () => {
    window.location.hash = "/home?care=not-a-moment";
    render(<App />);

    expect(await screen.findByText("客厅片段在日常阈值内")).toBeDefined();
    expect(screen.getByLabelText("Room Echo Agent 的模拟照护解释")).toBeDefined();
    expect(document.querySelector('[data-care-simulation="true"]')).not.toBeNull();
    expect(apiMocks.fetchCareScenario).toHaveBeenCalledTimes(1);
  });

  it("keeps malformed care JSON in the same fail-closed home composition", async () => {
    apiMocks.fetchCareScenario.mockResolvedValueOnce({
      schema_version: "simulated-care-scenario.v2",
      moments: [{ moment: "routine" }],
    });
    render(<App />);

    expect(await screen.findByText("暂时无法判断")).toBeDefined();
    expect(document.querySelectorAll('[data-action-source="care_workflow"]')).toHaveLength(4);
    expect(document.querySelectorAll('[data-action-status="withheld"]')).toHaveLength(4);
    const elements = [
      document.querySelector('[data-public-agent="room-echo"]'),
      document.querySelector(".agent-action-window"),
      document.querySelector(".digit-field"),
    ];
    for (const element of elements) {
      expect(element?.getAttribute("data-evidence-hash")).toBe("waiting");
      expect(element?.getAttribute("data-session-id")).toBe("waiting");
      expect(element?.getAttribute("data-window-id")).toBe("waiting");
    }
    expect(document.querySelector(".digit-field")?.getAttribute("data-life-active"))
      .toBe("false");
  });

  it("does not fabricate a memory while evidence is unavailable", () => {
    apiMocks.fetchCareScenario.mockReturnValueOnce(new Promise(() => undefined));
    render(<App />);
    expect(screen.getByLabelText(/证据不足，身体未完全成形/)).toBeDefined();
    expect(screen.queryByRole("button", { name: /保存这一刻/ })).toBeNull();
    expect(window.localStorage.length).toBe(0);
    expect(window.location.hash).toBe("");
    const agent = document.querySelector('[data-public-agent="room-echo"]');
    const actions = document.querySelector(".agent-action-window");
    const field = document.querySelector(".digit-field");
    for (const element of [agent, actions, field]) {
      expect(element?.getAttribute("data-evidence-hash")).toBe("waiting");
      expect(element?.getAttribute("data-session-id")).toBe("waiting");
      expect(element?.getAttribute("data-window-id")).toBe("waiting");
    }
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
    window.location.hash = "/settings";
    render(<App />);
    const toggle = await screen.findByRole("checkbox", { name: /减少动态/ });
    fireEvent.click(toggle);
    expect(document.documentElement.classList.contains("reduced-motion")).toBe(true);
  });
});
