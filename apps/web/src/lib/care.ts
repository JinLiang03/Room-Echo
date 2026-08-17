import type {
  CareMomentFacts,
  SimulatedCareMoment,
  SimulatedCareScenario,
} from "../generated/contracts";
import type { AgentActionSuggestion } from "../components/AgentActionWindow";
import type { CareMomentKey } from "./care-state";
import type { CareLoadStatus } from "./care-state";

export const CARE_MOMENT_META: Record<
  CareMomentKey,
  { label: string; shortLabel: string; tone: string }
> = {
  routine: { label: "日常活动", shortLabel: "日常", tone: "normal" },
  bathroom_timeout: {
    label: "卫生间停留超时",
    shortLabel: "浴室超时",
    tone: "warning",
  },
  fall_drill: {
    label: "跌倒风险演练",
    shortLabel: "跌倒演练",
    tone: "urgent",
  },
  pet_night: {
    label: "夜间宠物活动",
    shortLabel: "夜间宠物",
    tone: "attention",
  },
};

export const CARE_MOMENT_ORDER: CareMomentKey[] = [
  "routine",
  "bathroom_timeout",
  "fall_drill",
  "pet_night",
];

export function nextCareMoment(current: CareMomentKey): CareMomentKey {
  const index = CARE_MOMENT_ORDER.indexOf(current);
  return CARE_MOMENT_ORDER[(index + 1) % CARE_MOMENT_ORDER.length];
}

const CARE_MOMENT_KEYS = new Set<CareMomentKey>(CARE_MOMENT_ORDER);

/** A narrow runtime gate for the untrusted JSON returned by the care API. */
export function isCareScenarioPayload(
  value: unknown,
): value is SimulatedCareScenario {
  if (!isRecord(value)) return false;
  if (
    value.schema_version !== "simulated-care-scenario.v2" ||
    value.simulation_only !== true ||
    value.source_mode !== "mock" ||
    value.device_execution_enabled !== false ||
    typeof value.scenario_id !== "string" ||
    !Array.isArray(value.moments) ||
    value.moments.length !== CARE_MOMENT_ORDER.length
  ) {
    return false;
  }
  const moments = value.moments.filter(isCareMomentPayload);
  return (
    moments.length === CARE_MOMENT_ORDER.length &&
    new Set(moments.map((moment) => moment.moment)).size ===
      CARE_MOMENT_ORDER.length
  );
}

function isCareMomentPayload(value: unknown): value is SimulatedCareMoment {
  if (!isRecord(value) || !CARE_MOMENT_KEYS.has(value.moment as CareMomentKey)) {
    return false;
  }
  if (
    typeof value.event_id !== "string" ||
    typeof value.timeline_entry_id !== "string" ||
    typeof value.evidence_hash !== "string" ||
    typeof value.headline !== "string" ||
    typeof value.conclusion !== "string" ||
    (value.interpretation_status !== "supported" &&
      value.interpretation_status !== "unknown") ||
    !Array.isArray(value.what_agent_does_not_know) ||
    !Array.isArray(value.suggestions) ||
    value.suggestions.length !== 4 ||
    !value.suggestions.every(isCareSuggestionPayload)
  ) {
    return false;
  }
  const evidence = value.evidence_core;
  return (
    isRecord(evidence) &&
    evidence.schema_version === "care-evidence-core.v2" &&
    Array.isArray(evidence.external_observations) &&
    evidence.external_observations.every(
      (observation) =>
        isRecord(observation) &&
        (observation.quality_status === "ok" ||
          observation.quality_status === "degraded"),
    ) &&
    isSignalTripletPayload(evidence.proxy_triplet)
  );
}

function isCareSuggestionPayload(value: unknown): boolean {
  return (
    isRecord(value) &&
    typeof value.suggestion_id === "string" &&
    typeof value.kind === "string" &&
    typeof value.title === "string" &&
    typeof value.preview_copy === "string" &&
    (value.execution_status === "simulated_preview" ||
      value.execution_status === "withheld") &&
    typeof value.action_confidence === "number" &&
    typeof value.sensor_confidence_cap === "number"
  );
}

function isSignalTripletPayload(value: unknown): boolean {
  if (!isRecord(value)) return false;
  const motion = value.motion;
  const occupancy = value.occupancy_density;
  const depth = value.depth_zone;
  return (
    value.schema_version === "1.0.0" &&
    value.source_mode === "mock" &&
    typeof value.session_id === "string" &&
    typeof value.window_id === "string" &&
    typeof value.started_at === "string" &&
    typeof value.ended_at === "string" &&
    typeof value.sensor_confidence_cap === "number" &&
    (value.status === "ok" || value.status === "degraded") &&
    isRecord(motion) &&
    typeof motion.value === "number" &&
    typeof motion.state === "string" &&
    typeof motion.confidence === "number" &&
    isProbabilitySignalPayload(occupancy, ["low", "medium", "high", "unknown"]) &&
    isProbabilitySignalPayload(depth, ["near", "mid", "far", "unknown"])
  );
}

function isProbabilitySignalPayload(
  value: unknown,
  keys: readonly string[],
): boolean {
  if (!isRecord(value)) return false;
  const probabilities = value.probabilities;
  if (!isRecord(probabilities)) return false;
  return (
    typeof value.state === "string" &&
    typeof value.confidence === "number" &&
    keys.every((key) => typeof probabilities[key] === "number")
  );
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

const ICON_ROLE_BY_KIND: Record<
  SimulatedCareMoment["suggestions"][number]["kind"],
  NonNullable<AgentActionSuggestion["iconRole"]>
> = {
  ambient_light_preview: "soundscape",
  voice_checkin_preview: "biota",
  family_notification_draft: "psyche",
  robot_inspection_preview: "architecture",
};

export function selectedCareMoment(
  scenario: SimulatedCareScenario | null,
  selected: CareMomentKey,
): SimulatedCareMoment | null {
  if (!scenario || !Array.isArray(scenario.moments)) return null;
  return scenario.moments.find((moment) => moment.moment === selected) ?? null;
}

/**
 * Only a fully supported, fresh simulated frame may reach the public care UI.
 * A degraded/unknown frame remains part of the auditable scenario response,
 * but it must project as unknown rather than borrow another stream or retain
 * affirmative copy from an earlier care moment.
 */
export function supportedCareMoment(
  moment: SimulatedCareMoment | null,
): SimulatedCareMoment | null {
  if (!moment || moment.interpretation_status !== "supported") return null;
  const evidence = moment.evidence_core;
  const triplet = evidence?.proxy_triplet;
  if (!triplet || triplet.status !== "ok") return null;
  if (!Array.isArray(evidence.external_observations)) return null;
  if (
    evidence.external_observations.some(
      (observation) => observation.quality_status !== "ok",
    )
  ) {
    return null;
  }
  return moment;
}

export function careSuggestions(
  moment: SimulatedCareMoment | null,
): AgentActionSuggestion[] | undefined {
  if (!moment) return undefined;
  return moment.suggestions.map((suggestion) => ({
    id: suggestion.suggestion_id,
    actionKind: suggestion.kind,
    label: suggestion.title,
    description: suggestion.preview_copy,
    status: suggestion.execution_status,
    source: "care_workflow",
    boundary: careSuggestionBoundary(suggestion),
    iconRole: ICON_ROLE_BY_KIND[suggestion.kind],
    confidence: suggestion.action_confidence,
    sensorCap: suggestion.sensor_confidence_cap,
  }));
}

export function waitingCareSuggestions(
  status: CareLoadStatus,
): AgentActionSuggestion[] {
  const prefix = status === "unavailable" ? "场景暂不可用" : "等待证据";
  return [
    {
      id: "care-waiting-light",
      actionKind: "ambient_light_preview",
      label: "等待环境光建议",
      description: prefix,
      status: "withheld",
      source: "care_workflow",
      boundary: `${prefix} · 未连接灯具`,
      iconRole: "soundscape",
    },
    {
      id: "care-waiting-voice",
      actionKind: "voice_checkin_preview",
      label: "等待语音建议",
      description: prefix,
      status: "withheld",
      source: "care_workflow",
      boundary: `${prefix} · 未连接音箱`,
      iconRole: "biota",
    },
    {
      id: "care-waiting-family",
      actionKind: "family_notification_draft",
      label: "等待家属消息建议",
      description: prefix,
      status: "withheld",
      source: "care_workflow",
      boundary: `${prefix} · 未发送消息`,
      iconRole: "psyche",
    },
    {
      id: "care-waiting-robot",
      actionKind: "robot_inspection_preview",
      label: "等待机器人建议",
      description: prefix,
      status: "withheld",
      source: "care_workflow",
      boundary: `${prefix} · 未创建任务`,
      iconRole: "architecture",
    },
  ];
}

function careSuggestionBoundary(
  suggestion: SimulatedCareMoment["suggestions"][number],
): string {
  if (suggestion.execution_status === "withheld") {
    if (suggestion.kind === "family_notification_draft") {
      return "已暂缓 · 未发送消息";
    }
    if (suggestion.kind === "robot_inspection_preview") {
      return "已暂缓 · 未创建任务";
    }
    return "已暂缓 · 未连接设备";
  }
  if (suggestion.kind === "ambient_light_preview") {
    return "模拟预览 · 未连接灯具";
  }
  if (suggestion.kind === "voice_checkin_preview") {
    return "模拟预览 · 未连接音箱";
  }
  if (suggestion.kind === "family_notification_draft") {
    return "模拟预览 · 未发送消息";
  }
  return "模拟预览 · 未创建任务";
}

export function careInputSummary(facts: CareMomentFacts): string {
  if (facts.input_sources.includes("simulated_manual_fall_drill_label")) {
    return "人工演练标签 + Wi-Fi 代理";
  }
  if (facts.input_sources.includes("simulated_external_multisensor_label")) {
    return "外部多传感器标签 + Wi-Fi 代理";
  }
  if (facts.input_sources.includes("simulated_external_zone_presence")) {
    return "外部区域标签 + Wi-Fi 代理";
  }
  return "Wi-Fi 三项代理信号";
}

export function careSourceLabel(
  source: SimulatedCareMoment["facts"]["input_sources"][number],
): string {
  const labels: Record<typeof source, string> = {
    simulated_wifi_proxy: "Wi-Fi 三项代理",
    simulated_external_zone_presence: "模拟区域存在标签",
    simulated_external_multisensor_label: "模拟宠物项圈 / 地垫标签",
    simulated_manual_fall_drill_label: "人工跌倒演练标签",
    simulated_care_rule: "用户设定照护规则",
    simulated_clock: "模拟系统时钟",
  };
  return labels[source];
}

export function formatCareTime(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "--:--";
  return new Intl.DateTimeFormat("zh-CN", {
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  }).format(date);
}

export function careMomentForTimelineEntry(
  scenario: SimulatedCareScenario,
  entryId: string,
): SimulatedCareMoment | null {
  return (
    scenario.moments.find((moment) => moment.timeline_entry_id === entryId) ?? null
  );
}
