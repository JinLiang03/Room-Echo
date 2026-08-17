import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { councilResults } from "../generated/fixtures";
import type { PublicAgentPresentation } from "../lib/agent-presentation";
import type { CouncilResult } from "../lib/types";
import { AgentActionWindow } from "./AgentActionWindow";

function agent(result: CouncilResult): PublicAgentPresentation {
  return {
    phase: "responding",
    phaseLabel: "完成判断",
    headline: "受限解释",
    explanation: "只使用封存证据。",
    uncertainty: "仍有边界。",
    cycleId: result.cycle_id,
    evidenceHash: result.evidence_hash,
    snapshot: null,
    finalConfidence: result.display_confidence,
    sensorCap: result.sensor_confidence_cap,
    result,
  };
}

const replayResult = councilResults[0] as CouncilResult;

describe("AgentActionWindow", () => {
  it("renders four bounded suggestions and labels only the contract preview as simulated", () => {
    const { container } = render(
      <AgentActionWindow agent={agent(replayResult)} sourceMode="replay" />,
    );

    expect(container.querySelectorAll(".action-suggestion")).toHaveLength(4);
    expect(container.firstElementChild?.getAttribute("data-suggestion-count")).toBe("4");
    expect(
      container.querySelector('[data-action-status="simulated_preview"]'),
    ).not.toBeNull();
    expect(
      screen.getByLabelText("数字生成式生物形态图标，非物种识别"),
    ).toBeDefined();
    expect(container.querySelector(".action-suggestion footer")).toBeNull();
    expect(screen.queryByText("ambient_light_preview")).toBeNull();
  });

  it("does not call a withheld Live action a simulation or execution", () => {
    const liveResult: CouncilResult = {
      ...replayResult,
      action_decision: {
        ...replayResult.action_decision,
        source_mode: "live",
        action_type: "stay_silent",
        execution_status: "withheld",
        target: "none",
        reason_code: "no_actuator_adapter",
        explanation: "真实设备适配器尚未启用，本轮保持静默。",
      },
    };
    const { container } = render(
      <AgentActionWindow agent={agent(liveResult)} sourceMode="live" />,
    );

    expect(container.querySelector('[data-action-status="withheld"]')).not.toBeNull();
    expect(screen.getByText("已暂缓 · 未触发设备")).toBeDefined();
  });

  it("accepts a backend-ready suggestion array and fills missing slots safely", () => {
    const { container } = render(
      <AgentActionWindow
        agent={agent(replayResult)}
        sourceMode="replay"
        suggestions={[
          {
            id: "care-one",
            actionKind: "care_check",
            label: "人工确认",
            description: "等待照护者确认。",
            status: "suggested",
            source: "care_workflow",
            boundary: "未发送消息",
            iconRole: "biota",
          },
        ]}
      />,
    );

    expect(container.querySelectorAll(".action-suggestion")).toHaveLength(4);
    expect(
      container.querySelector('[data-action-kind="care_check"]')?.getAttribute(
        "data-action-source",
      ),
    ).toBe("care_workflow");
    expect(screen.queryByText("等待照护者确认。")).toBeNull();
    expect(screen.getByText("建议 · 尚未执行")).toBeDefined();
    expect(container.querySelector(".action-suggestion footer")).toBeNull();
  });
});
