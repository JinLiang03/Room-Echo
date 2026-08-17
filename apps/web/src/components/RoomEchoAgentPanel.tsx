import type { SimulatedCareMoment } from "../generated/contracts";
import type { PublicAgentPresentation } from "../lib/agent-presentation";
import type { CareLoadStatus } from "../lib/care-state";

interface Props {
  agent: PublicAgentPresentation;
  careMoment?: SimulatedCareMoment | null;
  careMode?: boolean;
  careStatus?: CareLoadStatus;
}

export function RoomEchoAgentPanel({
  agent,
  careMoment = null,
  careMode = false,
  careStatus = "idle",
}: Props) {
  const waitingForCare = careMode && careMoment === null;
  const phase = careMoment ? carePhase(careMoment) : waitingForCare ? "unknown" : agent.phase;
  const headline = careMoment?.headline ?? (
    waitingForCare
      ? careStatus === "unavailable"
        ? "暂时无法判断"
        : "正在同步模拟居家信号"
      : agent.headline
  );
  const subtitle = concise(
    (careMoment ? careConclusion(careMoment) : null) ?? (
      waitingForCare
        ? careStatus === "unavailable"
          ? "模拟居家输入未到达或已失效，所有行动保持暂缓。"
          : "等待同一时刻的模拟输入，Agent 暂不形成结论。"
        : agent.explanation
    ),
    "正在根据当前代理信号形成受限解释。",
  );
  const statusOne = careMoment
    ? carePhaseLabel(careMoment)
    : waitingForCare
      ? careStatus === "unavailable" ? "场景暂不可用" : "等待当前证据"
    : concise(agent.phaseLabel, "等待判断");
  const statusTwo = careMoment
    ? concise(careMoment.what_agent_does_not_know[0], "仍需外部确认")
    : waitingForCare
      ? "未触发任何行动"
    : concise(agent.uncertainty, "证据不足时保持未知");
  const proxyTriplet = careMoment?.evidence_core.proxy_triplet ?? null;

  return (
    <section
      className={`room-agent room-agent-${phase}`}
      aria-label={
        careMode
          ? "Room Echo Agent 的模拟照护解释"
          : "Room Echo Agent 的实时解释"
      }
      aria-live="polite"
      data-public-agent="room-echo"
      data-cycle-id={
        careMode ? careMoment?.event_id ?? "waiting" : agent.cycleId ?? "waiting"
      }
      data-evidence-hash={
        careMode
          ? careMoment?.evidence_hash ?? "waiting"
          : agent.evidenceHash ?? "waiting"
      }
      data-window-id={
        careMode
          ? proxyTriplet?.window_id ?? "waiting"
          : agent.snapshot?.window_id ?? "waiting"
      }
      data-session-id={
        careMode
          ? proxyTriplet?.session_id ?? "waiting"
          : agent.snapshot?.session_id ?? "waiting"
      }
      data-care-simulation={careMode ? "true" : "false"}
      data-care-moment={careMoment?.moment ?? "waiting"}
    >
      <header className="room-agent-head">
        <div>
          <h1>{headline}</h1>
          <p className="room-agent-subtitle">{subtitle}</p>
        </div>
      </header>

      <ul className="room-agent-status" aria-label="Agent 的两项状态">
        <li>{statusOne}</li>
        <li>{statusTwo}</li>
      </ul>
    </section>
  );
}

function careConclusion(moment: SimulatedCareMoment): string {
  if (moment.moment === "routine") {
    return "模拟外部区域标签显示：客厅活动已持续 18 分钟，仍在 45 分钟日常阈值内。";
  }
  if (moment.moment === "bathroom_timeout") {
    return "模拟外部区域标签显示：卫生间停留 31 分钟，超过 20 分钟关注阈值。";
  }
  return moment.conclusion;
}

function concise(value: string | null | undefined, fallback: string): string {
  const text = value?.trim() || fallback;
  const first = text.split(/[。；\n]/u).find(Boolean) ?? fallback;
  return first.length > 34 ? `${first.slice(0, 34)}…` : first;
}

function carePhase(
  moment: SimulatedCareMoment,
): PublicAgentPresentation["phase"] {
  if (moment.severity === "normal") return "responding";
  if (moment.severity === "urgent_drill" || moment.severity === "warning") {
    return "responding";
  }
  return "checking";
}

function carePhaseLabel(moment: SimulatedCareMoment): string {
  if (moment.severity === "normal") return "日常 · 不打扰";
  if (moment.severity === "attention") return "已核对来源";
  if (moment.severity === "warning") return "需要先确认";
  return "高优先 · 演练";
}
