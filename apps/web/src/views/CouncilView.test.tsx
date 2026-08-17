import { describe, expect, it } from "vitest";
import { CouncilView } from "./CouncilView";
import { renderWithStream } from "../test-utils";
import { initialState } from "../lib/state";
import type { CycleView, StreamState } from "../lib/types";

function stateWithCycle(cycle: CycleView): StreamState {
  const state = initialState();
  return {
    ...state,
    council: {
      cycles: { [cycle.cycleId]: cycle },
      order: [cycle.cycleId],
      discussionUnavailable: false,
    },
  };
}

const cycle: CycleView = {
  cycleId: "cycle-0001",
  evidenceHash: "sha256:0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef",
  claims: [
    {
      schema_version: "agent-claim.v1",
      claim_id: "claim-1",
      cycle_id: "cycle-0001",
      agent_id: "agent-motion",
      agent_version: "v1",
      role: "feng_shui",
      lens: "metaphor",
      kind: "observation",
      state: "accepted",
      proposition: "动态扰动与 moving 状态一致。",
      stance: "supports",
      evidence_refs: ["evidence://sha256:abc/signals/motion/value"],
      analysis_steps: [
        {
          step_id: "observe",
          phase: "observe",
          title: "观察信号",
          text: "读取证据包标量: motion=moving。",
          evidence_refs: ["evidence://sha256:abc/signals/motion/state"],
        },
        {
          step_id: "conclude",
          phase: "conclude",
          title: "结论",
          text: "收敛为命题: 动态扰动与 moving 状态一致。",
          evidence_refs: ["evidence://sha256:abc/signals/motion/state"],
        },
      ],
      systematic_reading: {
        headline: "动态扰动与 moving 状态一致。",
        scene_sketch: "如果此刻有风,它会在近前慢慢转向。",
        layers: [
          {
            signal: "motion",
            state: "moving",
            metaphor: "气动",
            explanation: "气流意象读作「流动」:运动标量描述的是代理变化。",
          },
          {
            signal: "occupancy",
            state: "low",
            metaphor: "气散/开阔",
            explanation: "占用密度描述遮挡与空间充盈度,不是人数。",
          },
          {
            signal: "depth",
            state: "near",
            metaphor: "明堂近",
            explanation: "纵深是相对层级,不是米制距离。",
          },
        ],
        narrative: "按青禾的读法,这间房的气是缓的、散的、近的。",
        boundary_notes: ["气、明堂、吉凶都是文化隐喻。"],
        multimodal_hints: ["若接入声学模态,可对照环境声级与“气动”意象。"],
      },
      falsification_test: "重复测量验证。",
      reasoning_summary: "仅引用当前包。",
    },
  ],
  challenges: [],
  rejections: [
    {
      schema_version: "policy-rejection.v1",
      rejection_id: "rejection-1",
      cycle_id: "cycle-0001",
      target_id: "claim-0",
      agent_id: "agent-feng_shui-bad",
      role: "feng_shui",
      reason_code: "forbidden_wall_presence",
      detail: "越权主张被拒绝。",
      rejected_at: "2026-08-06T12:00:00Z",
    },
  ],
  result: {
    schema_version: "council-result.v1",
    cycle_id: "cycle-0001",
    evidence_hash: "sha256:abc",
    status: "ambiguous",
    headline: "证据解读存在未解决质疑",
    summary: "存在未解决挑战。",
    sensor_confidence_cap: 0.8,
    model_support: 0.8,
    display_confidence: 0.6,
    interpretation_agreement: {
      participants: 4,
      supporting: 2,
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
  },
};

describe("CouncilView", () => {
  it("shows discussion unavailable when no cycles exist", () => {
    const { getByText } = renderWithStream(<CouncilView />, initialState());
    expect(getByText("讨论不可用")).toBeDefined();
  });

  it("renders claims, rejections, and final result", () => {
    const { getByText } = renderWithStream(
      <CouncilView />,
      stateWithCycle(cycle),
    );
    expect(getByText("动态扰动与 moving 状态一致。")).toBeDefined();
    expect(getByText("forbidden_wall_presence")).toBeDefined();
    expect(getByText("证据解读存在未解决质疑")).toBeDefined();
  });

  it("renders the multi-step analysis trace under the claim", () => {
    const { getByText, getAllByLabelText } = renderWithStream(
      <CouncilView />,
      stateWithCycle(cycle),
    );
    expect(getByText("观察信号")).toBeDefined();
    expect(getByText("读取证据包标量: motion=moving。")).toBeDefined();
    expect(getByText("收敛为命题: 动态扰动与 moving 状态一致。")).toBeDefined();
    const stepLists = getAllByLabelText("分析轨迹");
    expect(stepLists.length).toBe(1);
    expect(stepLists[0].children.length).toBe(2);
  });

  it("renders the systematic reading block", () => {
    const { getByText, getByLabelText } = renderWithStream(
      <CouncilView />,
      stateWithCycle(cycle),
    );
    expect(getByLabelText("系统解读")).toBeDefined();
    expect(getByText("如果此刻有风,它会在近前慢慢转向。")).toBeDefined();
    expect(getByText("气动")).toBeDefined();
    expect(getByText("气散/开阔")).toBeDefined();
    expect(getByText("明堂近")).toBeDefined();
    expect(getByText("按青禾的读法,这间房的气是缓的、散的、近的。")).toBeDefined();
  });

});
