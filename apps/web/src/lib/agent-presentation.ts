import type { CycleView, SignalTriplet, StreamState } from "./types";

export type PublicAgentPhase =
  | "waiting"
  | "observing"
  | "checking"
  | "responding"
  | "unknown";

export interface PublicAgentPresentation {
  phase: PublicAgentPhase;
  phaseLabel: string;
  headline: string;
  explanation: string;
  uncertainty: string;
  cycleId: string | null;
  evidenceHash: string | null;
  snapshot: SignalTriplet | null;
  finalConfidence: number | null;
  sensorCap: number | null;
  result: CycleView["result"];
}

/**
 * Project the auditable internal Council into one public Room Echo voice.
 * The projection never merges readings from different evidence cycles and it
 * never promotes Agent agreement into sensor confidence.
 */
export function publicAgentPresentation(
  state: StreamState,
): PublicAgentPresentation {
  const cycle = newestCycle(state);
  // Once a Council cycle exists, only its own sealed SignalTriplet may
  // accompany its explanation. Never borrow a newer live triplet for an
  // older result during late join, replay seek, or snapshot hydration.
  const snapshot = cycle ? cycle.signalSnapshot ?? null : state.triplet;
  const result =
    cycle?.result &&
    (!cycle.evidenceHash || cycle.result.evidence_hash === cycle.evidenceHash)
      ? cycle.result
      : null;

  if (state.stale || state.connection === "offline") {
    return {
      phase: "unknown",
      phaseLabel: "连接中断",
      headline: "我先停下来，不沿用上一刻。",
      explanation:
        "当前没有新鲜的空间代理信号；旧状态已被清除，不会被当成此刻继续解释。",
      uncertainty: "等待数据恢复后，我会从新的封存证据重新开始。",
      cycleId: cycle?.cycleId ?? null,
      evidenceHash: cycle?.evidenceHash ?? null,
      snapshot: null,
      finalConfidence: null,
      sensorCap: null,
      result: null,
    };
  }

  if (!snapshot) {
    return {
      phase: "waiting",
      phaseLabel: "等待信号",
      headline: "我还没有收到足够的空间变化。",
      explanation:
        "Room Echo 只读取活动强度、遮挡/空间占用代理和相对纵深代理，不会用空白补成结论。",
      uncertainty: "公开体验为模拟或回放时，页面会明确标注数据来源。",
      cycleId: null,
      evidenceHash: null,
      snapshot: null,
      finalConfidence: null,
      sensorCap: null,
      result: null,
    };
  }

  if (!cycle) {
    return {
      phase: "observing",
      phaseLabel: "正在观察",
      headline: "我正在把变化整理成一份可复核的证据。",
      explanation: describeSnapshot(snapshot),
      uncertainty: "证据尚未封存；我不会提前给出行动结论。",
      cycleId: null,
      evidenceHash: null,
      snapshot,
      finalConfidence: null,
      sensorCap: snapshot.sensor_confidence_cap,
      result: null,
    };
  }

  if (!result) {
    const hasChallenge = cycle.challenges.length > 0;
    return {
      phase: hasChallenge ? "checking" : "observing",
      phaseLabel: hasChallenge ? "正在复核" : "正在解释",
      headline: hasChallenge
        ? "我正在排除干扰，还不急着行动。"
        : "我正在理解这一刻为什么发生变化。",
      explanation: describeSnapshot(snapshot),
      uncertainty: hasChallenge
        ? readableChallenge(cycle)
        : "内部审议仍在进行；信号动画不会等待这一步。",
      cycleId: cycle.cycleId,
      evidenceHash: cycle.evidenceHash ?? null,
      snapshot,
      finalConfidence: null,
      sensorCap: snapshot.sensor_confidence_cap,
      result: null,
    };
  }

  if (result.status === "unavailable") {
    return {
      phase: "unknown",
      phaseLabel: "证据不足",
      headline: "我不知道，所以先不行动。",
      explanation:
        result.life_interaction?.message ??
        "当前质量门没有通过；这一刻保持未知。",
      uncertainty:
        result.limitations?.[0] ??
        "代理信号不可用时，不会由 Agent 语言补全。",
      cycleId: cycle.cycleId,
      evidenceHash: result.evidence_hash,
      snapshot,
      finalConfidence: result.display_confidence,
      sensorCap: result.sensor_confidence_cap,
      result,
    };
  }

  const ambiguous = result.status === "ambiguous";
  return {
    phase: ambiguous ? "checking" : "responding",
    phaseLabel: ambiguous ? "仍在确认" : "完成判断",
    headline:
      result.life_interaction?.state_label ??
      (ambiguous ? "这一刻仍有歧义" : result.headline),
    explanation:
      result.life_interaction?.message ?? result.headline,
    uncertainty: ambiguous
      ? readableChallenge(cycle)
      : result.limitations?.[0] ??
        "这是代理信号的受限解释，不是摄像影像或人物判断。",
    cycleId: cycle.cycleId,
    evidenceHash: result.evidence_hash,
    snapshot,
    finalConfidence: result.display_confidence,
    sensorCap: result.sensor_confidence_cap,
    result,
  };
}

function newestCycle(state: StreamState): CycleView | null {
  for (let index = state.council.order.length - 1; index >= 0; index -= 1) {
    const cycle = state.council.cycles[state.council.order[index]];
    if (cycle) return cycle;
  }
  return null;
}

function readableChallenge(cycle: CycleView): string {
  const challenge =
    cycle.challenges.find((item) => item.status === "open") ??
    cycle.challenges.at(-1);
  if (!challenge) {
    return "我会等待下一周期，确认这不是一次短暂的无线扰动。";
  }
  return challenge.assessment?.rationale ?? challenge.statement;
}

function describeSnapshot(snapshot: SignalTriplet): string {
  const motion = {
    idle: "趋于平稳",
    micro_motion: "轻微变化",
    moving: "持续变化",
    fast_change: "快速变化",
    unknown: "未知",
  }[snapshot.motion.state];
  const occupancy = {
    low: "偏低",
    medium: "居中",
    high: "偏高",
    unknown: "未知",
  }[snapshot.occupancy_density.state];
  const depth = {
    near: "偏近",
    mid: "居中",
    far: "偏远",
    unknown: "未知",
  }[snapshot.depth_zone.state];
  return `我观察到活动${motion}，遮挡/空间占用代理${occupancy}，相对纵深${depth}。`;
}
