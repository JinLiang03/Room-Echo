import type { AgentActionDecision } from "../generated/contracts";
import type { PublicAgentPresentation } from "../lib/agent-presentation";
import { DigitSectionMark } from "./DigitSectionMark";

interface Props {
  agent: PublicAgentPresentation;
  sourceMode: string | null;
  /** Future care endpoints can supply their own bounded list through this seam. */
  suggestions?: readonly AgentActionSuggestion[];
  evidenceHash?: string | null;
  sessionId?: string | null;
  windowId?: string | null;
}

export type AgentSuggestionStatus =
  | AgentActionDecision["execution_status"]
  | "suggested"
  | "pending"
  | "unavailable";

export type AgentSuggestionSource =
  | "agent_contract"
  | "safe_fallback"
  | "care_workflow";

export interface AgentActionSuggestion {
  id: string;
  actionKind: string;
  label: string;
  description: string;
  status: AgentSuggestionStatus;
  source: AgentSuggestionSource;
  /** Human-readable execution boundary; it must never be inferred from prose. */
  boundary: string;
  iconRole?: "biota" | "soundscape" | "psyche" | "architecture";
  confidence?: number | null;
  sensorCap?: number | null;
}

const ACTION_LABELS: Record<string, string> = {
  stay_silent: "保持安静",
  wait_and_observe: "继续观察",
  ambient_light_preview: "预演环境引导光",
};

export function AgentActionWindow({
  agent,
  sourceMode,
  suggestions,
  evidenceHash,
  sessionId,
  windowId,
}: Props) {
  const cards = normalizeSuggestions(
    suggestions ?? fallbackSuggestions(agent, sourceMode),
  );

  return (
    <section
      className="agent-action-window"
      aria-label="Room Echo Agent 的四项行动建议"
      aria-live="polite"
      data-suggestion-count={cards.length}
      data-evidence-hash={evidenceHash ?? agent.evidenceHash ?? "waiting"}
      data-session-id={sessionId ?? agent.snapshot?.session_id ?? "waiting"}
      data-window-id={windowId ?? agent.snapshot?.window_id ?? "waiting"}
    >
      <div className="action-suggestion-grid">
        {cards.map((suggestion) => (
          <article
            key={suggestion.id}
            className={`action-suggestion action-${suggestion.status}`}
            data-action-kind={suggestion.actionKind}
            data-action-status={suggestion.status}
            data-action-source={suggestion.source}
          >
            <div className="action-suggestion-top">
              <DigitSectionMark
                role={suggestion.iconRole ?? "architecture"}
                seed={`${suggestion.id}-${suggestion.actionKind}`}
                size="small"
                label={
                  suggestion.iconRole === "biota"
                    ? "数字生成式生物形态图标，非物种识别"
                    : undefined
                }
              />
            </div>
            <strong>{suggestion.label}</strong>
            <p>{tileDescription(suggestion)}</p>
          </article>
        ))}
      </div>

    </section>
  );
}

function fallbackSuggestions(
  agent: PublicAgentPresentation,
  sourceMode: string | null,
): AgentActionSuggestion[] {
  const decision = agent.result?.action_decision;
  const status = decision?.execution_status ?? "pending";
  const actionKind = decision?.action_type ?? "wait_and_observe";
  const unknownReason =
    agent.phase === "unknown"
      ? "证据不足；不会把未知补成行动。"
      : "等待受限策略完成本轮判断。";

  return [
    {
      id: decision?.decision_id ?? "current-policy",
      actionKind,
      label: ACTION_LABELS[actionKind] ?? "暂缓行动",
      description: decision?.explanation ?? unknownReason,
      status,
      source: "agent_contract",
      boundary: actionBoundary(status, sourceMode),
      iconRole: "biota",
      confidence: decision?.decision_confidence ?? null,
      sensorCap: decision?.sensor_confidence_cap ?? null,
    },
    {
      id: "observe-longer",
      actionKind: "wait_and_observe",
      label: "延长观察窗口",
      description: "继续积累连续代理信号，再决定是否升级处理。",
      status: "withheld",
      source: "safe_fallback",
      boundary: "已暂缓 · 继续观察",
      iconRole: "soundscape",
    },
    {
      id: "human-review",
      actionKind: "caregiver_review_placeholder",
      label: "请照护者复核",
      description: "待场景规则接入后，先由人确认再触发后续流程。",
      status: "withheld",
      source: "safe_fallback",
      boundary: "已暂缓 · 未发送消息",
      iconRole: "psyche",
    },
    {
      id: "device-handoff",
      actionKind: "device_handoff_placeholder",
      label: "准备设备协同",
      description: "为智能家居或居家机器人保留受控指令接口。",
      status: "withheld",
      source: "safe_fallback",
      boundary: "已暂缓 · 未连接设备",
      iconRole: "architecture",
    },
  ];
}

function normalizeSuggestions(
  suggestions: readonly AgentActionSuggestion[],
): AgentActionSuggestion[] {
  const safe = suggestions.slice(0, 4);
  const fallback = fallbackSuggestionSlots();
  while (safe.length < 4) safe.push(fallback[safe.length]);
  return safe;
}

function fallbackSuggestionSlots(): AgentActionSuggestion[] {
  return [0, 1, 2, 3].map((index) => ({
    id: `empty-suggestion-${index}`,
    actionKind: "unavailable",
    label: "等待建议",
    description: "当前没有可验证的场景建议。",
    status: "unavailable",
    source: "safe_fallback",
    boundary: "未触发任何设备",
    iconRole: "architecture",
  }));
}

function actionBoundary(
  status: AgentSuggestionStatus,
  sourceMode: string | null,
): string {
  if (status === "withheld") return "已暂缓 · 未触发设备";
  if (status === "simulated_preview") return "模拟预览 · 未连接设备";
  if (sourceMode === "live") return "真实设备未启用";
  return "等待策略 · 未触发设备";
}

function tileDescription(suggestion: AgentActionSuggestion): string {
  if (
    suggestion.status === "simulated_preview" ||
    suggestion.status === "withheld" ||
    suggestion.status === "unavailable"
  ) {
    return suggestion.boundary;
  }
  if (suggestion.status === "suggested") return "建议 · 尚未执行";
  if (suggestion.status === "pending") return "等待策略 · 尚未执行";
  return suggestion.description;
}
