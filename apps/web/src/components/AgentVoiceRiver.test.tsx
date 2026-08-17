import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { initialState } from "../lib/state";
import type {
  AgentChallenge,
  AgentClaim,
  CouncilResult,
  CycleView,
  SignalTriplet,
  StreamState,
} from "../lib/types";
import { AgentVoiceRiver } from "./AgentVoiceRiver";

function claim(
  cycleId: string,
  role: AgentClaim["role"],
  proposition: string,
  continuity?: NonNullable<AgentClaim["continuity"]>,
): AgentClaim {
  return {
    schema_version: "agent-claim.v1",
    claim_id: `${cycleId}-${role}`,
    cycle_id: cycleId,
    agent_id: `agent-${role}`,
    agent_version: "test-v1",
    role,
    lens: "metaphor",
    kind: "observation",
    state: "proposed",
    proposition,
    stance: "supports",
    evidence_refs: ["evidence://sha256:test/signals/motion/value"],
    counter_evidence_refs: [],
    sources: [],
    assumptions: [],
    alternative_explanations: [],
    falsification_test: "等待下一窗口复核。",
    reasoning_summary: "仅使用当前封存证据。",
    continuity,
  };
}

function challenge(cycleId: string): AgentChallenge {
  return {
    schema_version: "agent-challenge.v1",
    challenge_id: `${cycleId}-challenge`,
    target_claim_id: `${cycleId}-architecture`,
    challenger_agent_id: "agent-skeptic",
    category: "missing_evidence",
    proposed_severity: "material",
    statement: "当前信号质量不足以排除环境干扰。",
    evidence_refs: ["evidence://sha256:test/quality/overall_status"],
    resolution_test: "等待更高质量窗口。",
    status: "open",
    assessment: {
      schema_version: "skeptic-assessment.v1",
      evidence_status: "limited",
      evidence_label: "证据有限",
      withhold_judgment: true,
      rationale: "当前信号质量不足以排除环境干扰。",
      next_validation: "等待更高质量窗口。",
    },
  };
}

function result(cycleId: string): CouncilResult {
  return {
    schema_version: "council-result.v1",
    cycle_id: cycleId,
    evidence_hash: "sha256:test",
    status: "ambiguous",
    headline: "当前代理信号仍有歧义",
    summary: "活动变化存在，但环境干扰尚未排除。",
    sensor_confidence_cap: 0.72,
    model_support: 0.68,
    display_confidence: 0.61,
    interpretation_agreement: {
      participants: 7,
      supporting: 5,
      contradicting: 1,
      unresolved_challenges: 1,
      agreement_ratio: 0.71,
    },
    sound_motion: {
      schema_version: "sound-consensus-motion.v1",
      rhythm: "急拍",
      pitch: "高",
      distance: "近",
      thickness: "厚",
      synchrony: "松散",
    },
    life_interaction: {
      schema_version: "spatial-life-interaction.v1",
      state: "floating",
      state_label: "仍在漂浮",
      message: "我仍在漂浮：活动变化存在，但环境干扰尚未排除。",
      wish: "请保持房间条件不变，让我再观察一个周期。",
      effect: "float",
    },
    provenance: {
      contracts_version: "1.0.0",
      features_version: "features-v2",
      calibration_profile_id: "demo_room_v1",
      policy_version: "policy-v1",
      generated_at: "2026-08-10T00:00:00Z",
    },
  };
}

function cycle(
  cycleId: string,
  patch: Partial<CycleView> = {},
): CycleView {
  return {
    cycleId,
    evidenceHash: "sha256:test",
    startedAt: "2026-08-10T00:00:00Z",
    claims: [],
    challenges: [],
    rejections: [],
    result: null,
    ...patch,
  };
}

function stateWithCycles(cycles: CycleView[]): StreamState {
  const state = initialState();
  return {
    ...state,
    connection: "online",
    council: {
      cycles: Object.fromEntries(cycles.map((item) => [item.cycleId, item])),
      order: cycles.map((item) => item.cycleId),
      discussionUnavailable: false,
    },
  };
}

const reactiveTriplet: SignalTriplet = {
  schema_version: "1.0.0",
  session_id: "session-live",
  window_id: "window-live",
  source_mode: "replay",
  started_at: "2026-08-10T00:00:00Z",
  ended_at: "2026-08-10T00:00:00.250Z",
  motion: { value: 0.91, state: "fast_change", confidence: 0.78 },
  occupancy_density: {
    probabilities: { low: 0.05, medium: 0.15, high: 0.76, unknown: 0.04 },
    state: "high",
    confidence: 0.76,
  },
  depth_zone: {
    probabilities: { near: 0.72, mid: 0.18, far: 0.06, unknown: 0.04 },
    state: "near",
    confidence: 0.72,
  },
  sensor_confidence_cap: 0.72,
  evidence_refs: ["evidence://sha256:test/signals"],
  status: "ok",
};

describe("AgentVoiceRiver", () => {
  it("switches to a newly started cycle before its claims have finished", () => {
    const oldCycle = cycle("cycle-old", {
      claims: [claim("cycle-old", "architecture", "上一轮观点不应继续冒充当前观点。")],
      result: result("cycle-old"),
    });
    const newCycle = cycle("cycle-new");

    const { container } = render(
      <AgentVoiceRiver state={stateWithCycles([oldCycle, newCycle])} />,
    );

    expect(container.querySelector("section")?.dataset.cycleId).toBe("cycle-new");
    expect(screen.getByText("新证据已封存 · 七个视角正在读取")).toBeDefined();
    expect(screen.queryByText("上一轮观点不应继续冒充当前观点。")).toBeNull();
    expect(
      screen.getByText("正在判断空间的流是聚、散、滞还是冲。"),
    ).toBeDefined();
  });

  it("uses real claims, the real skeptic challenge, and the real synthesis", () => {
    const current = cycle("cycle-live", {
      claims: [
        {
          ...claim("cycle-live", "architecture", "该视角：阻隔与相对纵深代理同时抬升。"),
          presentation: {
            schema_version: "specialist-presentation.v1",
            role: "architecture",
            contribution: "space_form",
            contribution_label: "看见空间的形",
            state: "tightening",
            state_label: "收紧",
            analysis: "当前房间的充盈代理偏高、相对纵深偏近；空间边界读作「收紧」。",
            effect: "contract",
          },
        },
      ],
      challenges: [challenge("cycle-live")],
      result: result("cycle-live"),
    });

    const { container } = render(
      <AgentVoiceRiver state={stateWithCycles([current])} />,
    );

    expect(
      screen.getByText("当前房间的充盈代理偏高、相对纵深偏近；空间边界读作「收紧」。"),
    ).toBeDefined();
    expect(screen.getByText(/证据是否充分：证据有限/)).toBeDefined();
    expect(screen.getByText(/下一步验证：等待更高质量窗口/)).toBeDefined();
    expect(screen.getByText(/我仍在漂浮：活动变化存在/)).toBeDefined();
    expect(screen.getByText("请保持房间条件不变，让我再观察一个周期。")).toBeDefined();
    expect(screen.getByText("看见空间的形 · 收紧 / 展开 / 阻断")).toBeDefined();
    expect(screen.getByText("看见空间的息 · 静息 / 惊跳 / 恢复")).toBeDefined();
    expect(screen.getByText("看见空间的流 · 聚 / 散 / 滞 / 冲")).toBeDefined();
    expect(screen.getByText("看见空间的势 · 安定 / 活跃 / 警觉 / 漂浮")).toBeDefined();
    expect(
      screen.getByText("把共识翻译成：节奏 / 音高 / 远近 / 厚薄 / 同步"),
    ).toBeDefined();
    expect(
      screen.getByText("证据是否充分 · 是否暂缓判断 · 下一步如何验证"),
    ).toBeDefined();
    expect(
      screen.getByText("以空间生命视角告诉你：现在的状态 · 希望如何与你互动"),
    ).toBeDefined();
    expect(container.textContent).not.toContain("该视角：");
    expect(screen.getByLabelText(/共识视觉运动：节奏急拍/)).toBeDefined();
    expect(screen.getByText("本轮综合完成 · 03/07 个视角已返回")).toBeDefined();
    expect(
      container
        .querySelector('[data-agent-index="6"]')
        ?.getAttribute("data-voice-source"),
    ).toBe("challenge");
    expect(
      container
        .querySelector('[data-agent-index="7"]')
        ?.getAttribute("data-voice-source"),
    ).toBe("result");
  });

  it("keeps an overreaching metric-depth sentence out of the live voice", () => {
    const overreach = ["距离约", "2.4", "米。"].join(" ");
    const current = cycle("cycle-safe", {
      claims: [
        claim("cycle-safe", "architecture", overreach),
      ],
    });

    render(<AgentVoiceRiver state={stateWithCycles([current])} />);

    expect(screen.queryByText(overreach)).toBeNull();
    expect(
      screen.getByText("相对纵深代理出现变化；不是米制距离，需要结合信号质量复核。"),
    ).toBeDefined();
  });

  it("turns audit identifiers into readable role and proxy language", () => {
    const internalChallenge = {
      ...challenge("cycle-readable"),
      assessment: undefined,
      statement:
        "针对 soundscape 当前主张 claim-cycle-0001-05(motion=idle、occupancy=low、depth=near、quality=ok)",
    };
    const internalResult = {
      ...result("cycle-readable"),
      life_interaction: undefined,
      summary: "architecture、biota、feng_shui、psyche、soundscape 从不同角度解释。",
    };
    const current = cycle("cycle-readable", {
      challenges: [internalChallenge],
      result: internalResult,
    });

    const { container } = render(
      <AgentVoiceRiver state={stateWithCycles([current])} />,
    );

    expect(container.textContent).not.toContain("claim-cycle-0001-05");
    expect(container.textContent).not.toContain("soundscape");
    expect(container.textContent).toContain("声景视角");
    expect(container.textContent).toContain("活动=趋于平稳");
    expect(container.textContent).toContain("相对纵深=偏近");
    expect(container.textContent).toContain("流动隐喻视角");
  });

  it("maps the three proxies to explicit narrative reactions without life claims", () => {
    const current = cycle("cycle-reactive", {
      signalSnapshot: reactiveTriplet,
    });
    const state = {
      ...stateWithCycles([current]),
      triplet: reactiveTriplet,
    };

    render(<AgentVoiceRiver state={state} />);

    expect(screen.getByLabelText(/叙事反应：收紧；阻隔与空间占用代理处于中高状态/)).toBeDefined();
    expect(screen.getByLabelText(/叙事反应：惊跳/)).toBeDefined();
    expect(screen.getByLabelText(/叙事反应：冲/)).toBeDefined();
    expect(screen.getByLabelText(/叙事反应：警觉/)).toBeDefined();
    expect(screen.getByLabelText(/叙事反应：涌动/)).toBeDefined();
    expect(
      screen.getByText(
        /状态词只是三项代理信号与质量边界的叙事映射；不代表检测到真实生命、意识、情绪或人物/,
      ),
    ).toBeDefined();
    expect(screen.getAllByLabelText(/使用的同封存数据快照/)).toHaveLength(7);
    expect(document.querySelectorAll("details.agent-voice-observation:not([open])")).toHaveLength(7);
    expect(screen.getAllByText(/快速变化/).length).toBeGreaterThanOrEqual(7);
    expect(screen.getAllByText(/上限 72%/)).toHaveLength(7);
  });

  it("marks a Council answer when the live field has advanced past its seal", () => {
    const current = cycle("cycle-lagged", {
      signalSnapshot: reactiveTriplet,
      claims: [claim("cycle-lagged", "architecture", "解释封存窗口。")],
    });
    const state = {
      ...stateWithCycles([current]),
      triplet: { ...reactiveTriplet, window_id: "window-newer" },
    };

    render(<AgentVoiceRiver state={state} />);

    expect(
      screen.getByText("Agent 正在解释上一封存时刻 · 01/07 个视角已返回"),
    ).toBeDefined();
    expect(screen.getAllByText("正在解释上一封存时刻")).toHaveLength(7);
  });

  it("shows a seven-second cross-cycle continuation without rewriting signals", () => {
    const continuity: NonNullable<AgentClaim["continuity"]> = {
      schema_version: "agent-continuity.v1",
      previous_cycle_id: "cycle-prior",
      previous_record_id: "claim-prior-architecture",
      previous_evidence_hash: `sha256:${"a".repeat(64)}`,
      relation: "intensified",
      changed_signals: ["motion", "occupancy"],
      summary: "递进增强:活动与占用代理较上一周期上升。",
    };
    const current = cycle("cycle-continuity", {
      analysisRefreshS: 7,
      signalSnapshot: reactiveTriplet,
      claims: [
        claim(
          "cycle-continuity",
          "architecture",
          "当前空间边界进一步收紧；先与下一周期对照。",
          continuity,
        ),
      ],
    });
    const state = {
      ...stateWithCycles([current]),
      triplet: reactiveTriplet,
    };

    const { container } = render(<AgentVoiceRiver state={state} />);

    expect(screen.getByText("约 7 秒递进一次")).toBeDefined();
    expect(screen.getByText("递进增强")).toBeDefined();
    expect(screen.getByText(continuity.summary)).toBeDefined();
    expect(
      screen.getByText("当前空间边界进一步收紧；先与下一周期对照。"),
    ).toBeDefined();
    expect(
      container.querySelector('[data-continuity-relation="intensified"]'),
    ).not.toBeNull();
  });
});
