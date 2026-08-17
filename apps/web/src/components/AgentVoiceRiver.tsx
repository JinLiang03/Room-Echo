import type { CSSProperties } from "react";
import { withoutPersonaNames } from "../lib/personas";
import type {
  AgentChallenge,
  AgentClaim,
  CouncilResult,
  CycleView,
  SignalTriplet,
  StreamState,
} from "../lib/types";

interface Props {
  state: StreamState;
  compact?: boolean;
}

const ROLE_ORDER = [
  "architecture",
  "biota",
  "feng_shui",
  "psyche",
  "soundscape",
  "skeptic",
  "fusion",
] as const;

type VoiceRole = (typeof ROLE_ORDER)[number];

interface VoiceReading {
  text: string;
  source: "claim" | "challenge" | "result" | "pending";
  revision: string;
  detail?: string;
  continuity?: NonNullable<AgentClaim["continuity"]>;
  presentation?: NonNullable<AgentClaim["presentation"]>;
  assessment?: NonNullable<AgentChallenge["assessment"]>;
  soundMotion?: NonNullable<CouncilResult["sound_motion"]>;
  lifeInteraction?: NonNullable<CouncilResult["life_interaction"]>;
}

interface AgentReaction {
  label: string;
  basis: string;
}

function latestDiscussion(state: StreamState): {
  cycle: CycleView | null;
  readings: Map<VoiceRole, VoiceReading>;
} {
  // Select the newest started cycle even before its first claim arrives. This
  // makes a real cycle.started event visible immediately instead of leaving
  // the previous cycle on screen until synthesis has finished.
  for (let index = state.council.order.length - 1; index >= 0; index -= 1) {
    const cycle = state.council.cycles[state.council.order[index]];
    if (!cycle) continue;
    return { cycle, readings: readingsForCycle(cycle) };
  }
  return { cycle: null, readings: new Map() };
}

function readingsForCycle(cycle: CycleView): Map<VoiceRole, VoiceReading> {
  const readings = new Map<VoiceRole, VoiceReading>();
  const rejectedTargets = new Set(
    cycle.rejections.map((rejection) => rejection.target_id),
  );
  for (const claim of cycle.claims) {
    if (
      claim.cycle_id !== cycle.cycleId ||
      !isVoiceRole(claim.role) ||
      claim.role === "skeptic" ||
      claim.role === "fusion" ||
      rejectedTargets.has(claim.claim_id)
    ) {
      continue;
    }
    readings.set(claim.role, claimReading(claim));
  }

  const challenge = currentChallenge(
    cycle.challenges.filter(
      (candidate) => !rejectedTargets.has(candidate.challenge_id),
    ),
  );
  if (challenge) {
    readings.set("skeptic", {
      text: skepticReadingText(challenge),
      source: "challenge",
      revision: challenge.challenge_id,
      detail: `${challenge.proposed_severity} · ${challenge.status}`,
      continuity: challenge.continuity ?? undefined,
      assessment: challenge.assessment ?? undefined,
    });
  }

  if (cycle.result?.cycle_id === cycle.cycleId) {
    readings.set("fusion", resultReading(cycle.result));
  }
  return readings;
}

function isVoiceRole(role: string): role is VoiceRole {
  return (ROLE_ORDER as readonly string[]).includes(role);
}

function claimReading(claim: AgentClaim): VoiceReading {
  return {
    text: safeVoiceText(claim.proposition),
    source: "claim",
    revision: `${claim.claim_id}:${claim.state}`,
    detail: `${claim.stance} · ${claim.state}`,
    continuity: claim.continuity ?? undefined,
    presentation: claim.presentation ?? undefined,
  };
}

function currentChallenge(challenges: AgentChallenge[]): AgentChallenge | undefined {
  return (
    challenges.find((challenge) => challenge.status === "open") ??
    challenges[challenges.length - 1]
  );
}

function resultReading(result: CouncilResult): VoiceReading {
  return {
    text: safeVoiceText(
      result.life_interaction?.message ?? result.summary ?? result.headline,
    ),
    source: "result",
    revision: `${result.cycle_id}:${result.provenance.generated_at}`,
    detail: `${result.status} · ${Math.round(result.display_confidence * 100)}%`,
    continuity: result.continuity ?? undefined,
    soundMotion: result.sound_motion ?? undefined,
    lifeInteraction: result.life_interaction ?? undefined,
  };
}

function pendingReading(role: VoiceRole, cycleId: string): VoiceReading {
  const text: Record<VoiceRole, string> = {
    architecture: "正在判断空间的形是收紧、展开还是阻断。",
    biota: "正在判断空间的息是静息、惊跳还是恢复。",
    feng_shui: "正在判断空间的流是聚、散、滞还是冲。",
    psyche: "正在判断空间的势是安定、活跃、警觉还是漂浮。",
    soundscape: "等待共识，再把它翻译成同步的视觉运动。",
    skeptic: "正在判断证据是否充分，以及是否应暂缓结论。",
    fusion: "等待各视角返回，再以空间生命的口吻回应你。",
  };
  return {
    text: text[role],
    source: "pending",
    revision: `${cycleId}:${role}:pending`,
  };
}

function safeVoiceText(text: string): string {
  // Keep the actual Council wording readable while preventing an accidental
  // UI claim of metric depth from becoming a user-facing fact.
  if (/距离\s*(?:约\s*)?\d+(?:\.\d+)?\s*(?:米|m)/i.test(text)) {
    return "相对纵深代理出现变化；不是米制距离，需要结合信号质量复核。";
  }
  return withoutPersonaNames(text)
    .replace(/^\s*(?:该视角|当前视角)\s*[:：]\s*/i, "")
    .replace(/([；;。]\s*)(?:该视角|当前视角)\s*[:：]\s*/gi, "$1")
    .replace(/claim-cycle-[\w-]+/gi, "本轮对应观点")
    .replace(/feng_shui/gi, "流动隐喻视角")
    .replace(/architecture/gi, "空间结构视角")
    .replace(/soundscape/gi, "声景视角")
    .replace(/biota/gi, "环境痕迹视角")
    .replace(/psyche/gi, "空间心理视角")
    .replace(/\bmotion\s*=/gi, "活动=")
    .replace(/\boccupancy\s*=/gi, "占用=")
    .replace(/\bdepth\s*=/gi, "相对纵深=")
    .replace(/\bquality\s*=/gi, "质量=")
    .replace(/motion_intensity/gi, "活动强度")
    .replace(/occupancy_density_proxy/gi, "阻隔与空间占用代理")
    .replace(/depth_zone_proxy/gi, "相对纵深代理")
    .replace(/fast_change/gi, "快速变化")
    .replace(/micro_motion/gi, "轻微变化")
    .replace(/\bmoving\b/gi, "持续变化")
    .replace(/\bidle\b/gi, "趋于平稳")
    .replace(/\blow\b/gi, "低")
    .replace(/\bmedium\b/gi, "中")
    .replace(/\bhigh\b/gi, "高")
    .replace(/\bnear\b/gi, "偏近")
    .replace(/\bmid\b/gi, "居中")
    .replace(/\bfar\b/gi, "偏远")
    .replace(/\bok\b/gi, "可用")
    .replace(/\bunknown\b/gi, "未知")
    .replace(/在场感/g, "空间充盈感")
    .replace(/(?:检测到|识别到)\s*(?:人|人物|人体|姿态|身份)/g, "感知到空间变化")
    .replace(/仿佛有人刚坐下又起身/g, "仿佛空间刚刚发生过变化")
    .replace(/有人(?:刚刚?|又)?(?:坐下|起身)/g, "空间发生变化");
}

function skepticReadingText(challenge: AgentChallenge): string {
  const assessment = challenge.assessment;
  if (!assessment) {
    return `证据是否充分：正在复核。是否暂缓判断：是。原因：${safeVoiceText(challenge.statement)}下一步验证：${safeVoiceText(challenge.resolution_test)}`;
  }
  return skepticReadingTextFromAssessment(assessment);
}

export function AgentVoiceRiver({ state, compact = false }: Props) {
  const { cycle, readings } = latestDiscussion(state);
  const returned = readings.size;
  const fieldHasAdvanced = Boolean(
    cycle?.signalSnapshot &&
      state.triplet &&
      cycle.signalSnapshot.window_id !== state.triplet.window_id,
  );
  const cycleState = liveCycleState(state, cycle, returned, fieldHasAdvanced);

  return (
    <section
      className={`agent-voice-river${compact ? " agent-voice-river-compact" : ""}`}
      aria-label="七个 Agent 实时观点"
      data-cycle-id={cycle?.cycleId ?? "waiting"}
      data-stream-state={
        state.connection === "offline" ? "offline" : state.stale ? "paused" : "live"
      }
    >
      <div className="agent-voice-live" role="status" aria-live="polite">
        <span className="agent-voice-live-dot" aria-hidden="true" />
        <span>{cycleState}</span>
        {cycle?.analysisRefreshS && (
          <span className="agent-voice-cadence">
            约 {cycle.analysisRefreshS.toFixed(0)} 秒递进一次
          </span>
        )}
      </div>
      <div className="agent-voice-grid">
        {ROLE_ORDER.map((role, index) => {
          const reading =
            readings.get(role) ?? pendingReading(role, cycle?.cycleId ?? "waiting");
          const hasReturned = reading.source !== "pending";
          const reaction = reading.lifeInteraction
            ? {
                label: reading.lifeInteraction.state_label,
                basis: reading.lifeInteraction.message,
              }
            : reading.presentation?.analysis
              ? {
                label: reading.presentation.state_label,
                basis: reading.presentation.analysis,
                }
              : reactionFor(
                  role,
                  cycle?.signalSnapshot ?? null,
                  cycle === null && state.stale,
                );
          const explanation = reactionExplanation(
            role,
            cycle?.signalSnapshot ?? null,
            reaction,
            reading,
          );
          return (
            <article
              className={`agent-voice-item agent-voice-${role}${hasReturned ? " is-returned is-recent" : " is-pending"}`}
              data-agent-index={index + 1}
              data-voice-source={reading.source}
              key={role}
              style={
                { "--voice-enter-delay": `${index * 70}ms` } as CSSProperties
              }
            >
              <div className="agent-voice-mark" aria-hidden="true">
                <span>{String(index + 1).padStart(2, "0")}</span>
              </div>
              <div className="agent-voice-copy">
                <div className="agent-voice-name">
                  <strong>{role.toUpperCase()}</strong>
                  <span className="agent-voice-contribution">
                    {contributionLabel(role)}
                  </span>
                  {hasReturned && (
                    <span className="agent-voice-update" key={`${reading.revision}:badge`}>
                      刚刚更新
                    </span>
                  )}
                </div>
                <AgentEvidenceSnapshot
                  cycle={cycle}
                  role={role}
                  fieldHasAdvanced={fieldHasAdvanced}
                />
                {reading.continuity && (
                  <div
                    className={`agent-voice-continuity is-${reading.continuity.relation}`}
                    data-continuity-relation={reading.continuity.relation}
                  >
                    <b>{continuityLabel(reading.continuity.relation)}</b>
                    <span>{reading.continuity.summary}</span>
                  </div>
                )}
                {role === "soundscape" ? (
                  <SoundConsensusMotion
                    motion={cycle?.result?.sound_motion ?? reading.soundMotion ?? null}
                    pending={!cycle?.result}
                    revision={reading.revision}
                  />
                ) : (
                  <p
                    className={hasReturned ? "has-voice" : "is-placeholder"}
                    aria-live="polite"
                    aria-atomic="true"
                  >
                    <span
                      className="agent-voice-reaction"
                      aria-label={`空间生命体叙事反应：${reaction.label}；${reaction.basis}`}
                      title={reaction.basis}
                    >
                      {role === "fusion" ? "空间生命状态" : "本轮状态"} · {reaction.label}
                    </span>
                    <span
                      className="agent-voice-content"
                      key={reading.revision}
                    >
                      {explanation}
                      {role === "fusion" && reading.lifeInteraction && (
                        <em className="agent-fusion-wish">
                          {reading.lifeInteraction.wish}
                        </em>
                      )}
                    </span>
                  </p>
                )}
                {reading.detail && <small>{reading.detail}</small>}
                {role !== "soundscape" && hasReturned && explanation !== reading.text && (
                  <details className="agent-voice-source-claim">
                    <summary>查看 Agent 审计原文</summary>
                    <p>{reading.text}</p>
                  </details>
                )}
              </div>
            </article>
          );
        })}
      </div>
      <p className="agent-voice-metaphor-boundary">
        “收紧、静息、聚、警觉”等状态词只是三项代理信号与质量边界的叙事映射；不代表检测到真实生命、意识、情绪或人物。
      </p>
    </section>
  );
}

function SoundConsensusMotion({
  motion,
  pending,
  revision,
}: {
  motion: NonNullable<CouncilResult["sound_motion"]> | null;
  pending: boolean;
  revision: string;
}) {
  const axes = [
    ["节奏", motion?.rhythm ?? "等待"],
    ["音高", motion?.pitch ?? "等待"],
    ["远近", motion?.distance ?? "等待"],
    ["厚薄", motion?.thickness ?? "等待"],
    ["同步", motion?.synchrony ?? "等待"],
  ] as const;
  return (
    <div
      className={`agent-sound-motion${pending ? " is-pending" : " is-ready"}`}
      aria-label={
        motion
          ? `共识视觉运动：节奏${motion.rhythm}，音高${motion.pitch}，远近${motion.distance}，厚薄${motion.thickness}，同步${motion.synchrony}`
          : "共识视觉运动等待 Fusion"
      }
      data-rhythm={motion?.rhythm ?? "waiting"}
      data-synchrony={motion?.synchrony ?? "waiting"}
      key={revision}
    >
      {axes.map(([label, value], index) => (
        <div className="agent-sound-axis" key={label}>
          <span>{label}</span>
          <i aria-hidden="true" style={{ "--sound-axis": index } as CSSProperties} />
          <strong>{value}</strong>
        </div>
      ))}
    </div>
  );
}

function AgentEvidenceSnapshot({
  cycle,
  role,
  fieldHasAdvanced,
}: {
  cycle: CycleView | null;
  role: VoiceRole;
  fieldHasAdvanced: boolean;
}) {
  const snapshot = cycle?.signalSnapshot;
  const evidenceHash = cycle?.evidenceHash ?? "";
  if (!cycle || !snapshot) {
    return (
      <details className="agent-voice-observation">
        <summary>查看本轮数据</summary>
        <div
          className="agent-voice-snapshot is-unavailable"
          aria-label={`${role} 的同封存数据快照不可用`}
        >
          同封存数据快照待恢复；不使用当前实时值代替。
        </div>
      </details>
    );
  }

  const occupancyProbability =
    snapshot.occupancy_density.probabilities[snapshot.occupancy_density.state];
  const depthProbability = snapshot.depth_zone.probabilities[snapshot.depth_zone.state];
  return (
    <details className="agent-voice-observation">
      <summary>查看本轮数据</summary>
      <div
        className="agent-voice-snapshot"
        aria-label={`${role} 使用的同封存数据快照`}
        data-cycle-id={cycle.cycleId}
        data-evidence-hash={evidenceHash}
        data-window-id={snapshot.window_id}
      >
        <span>
          <b>活动</b> {snapshot.motion.value.toFixed(2)} · {motionLabel(snapshot.motion.state)}
        </span>
        <span>
          <b>充盈</b> {occupancyLabel(snapshot.occupancy_density.state)} · {percent(occupancyProbability)}
        </span>
        <span>
          <b>纵深</b> {depthLabel(snapshot.depth_zone.state)} · {percent(depthProbability)}
        </span>
        <span>
          <b>质量</b> {qualityLabel(snapshot.status)} · 上限 {percent(snapshot.sensor_confidence_cap)}
        </span>
        <span className="agent-voice-snapshot-seal">
          {shortCycleId(cycle.cycleId)} · {shortEvidenceHash(evidenceHash)}
        </span>
        {fieldHasAdvanced && (
          <span className="agent-voice-snapshot-lag">正在解释上一封存时刻</span>
        )}
      </div>
    </details>
  );
}

function percent(value: number | undefined): string {
  return `${Math.round(Math.max(0, Math.min(1, value ?? 0)) * 100)}%`;
}

function motionLabel(state: SignalTriplet["motion"]["state"]): string {
  return {
    idle: "平稳",
    micro_motion: "轻微变化",
    moving: "持续变化",
    fast_change: "快速变化",
    unknown: "未知",
  }[state];
}

function occupancyLabel(
  state: SignalTriplet["occupancy_density"]["state"],
): string {
  return { low: "低", medium: "中", high: "高", unknown: "未知" }[state];
}

function depthLabel(state: SignalTriplet["depth_zone"]["state"]): string {
  return { near: "偏近", mid: "居中", far: "偏远", unknown: "未知" }[state];
}

function qualityLabel(state: SignalTriplet["status"]): string {
  return {
    ok: "可用",
    degraded: "降级",
    insufficient_signal: "证据不足",
    uncalibrated: "未标定",
  }[state];
}

function shortCycleId(cycleId: string): string {
  return cycleId.length <= 18 ? cycleId : `…${cycleId.slice(-16)}`;
}

function shortEvidenceHash(evidenceHash: string): string {
  if (!evidenceHash) return "evidence hash 待恢复";
  const clean = evidenceHash.replace(/^sha256:/, "");
  return `evidence ${clean.slice(0, 8)}`;
}

function reactionFor(
  role: VoiceRole,
  triplet: SignalTriplet | null,
  stale: boolean,
): AgentReaction {
  if (stale) {
    return { label: "停驻", basis: "数据流暂停，保留最近一次封存观点" };
  }
  if (
    !triplet ||
    triplet.status === "insufficient_signal" ||
    triplet.status === "uncalibrated"
  ) {
    return { label: "等待", basis: "当前证据不足，不生成空间反应" };
  }

  switch (role) {
    case "architecture":
      if (
        triplet.occupancy_density.state === "high" &&
        triplet.motion.state !== "moving" &&
        triplet.motion.state !== "fast_change"
      ) {
        return { label: "阻断", basis: "充盈代理偏高且活动没有持续迁移" };
      }
      if (triplet.occupancy_density.state === "high" || triplet.occupancy_density.state === "medium") {
        return { label: "收紧", basis: "阻隔与空间占用代理处于中高状态" };
      }
      if (triplet.occupancy_density.state === "low") {
        return { label: "展开", basis: "阻隔与空间占用代理偏低" };
      }
      return { label: "暂不判断", basis: "阻隔与空间占用代理未知" };
    case "biota":
      if (triplet.motion.state === "fast_change") {
        return { label: "惊跳", basis: "活动强度正在快速变化" };
      }
      if (triplet.motion.state === "moving") {
        return { label: "惊跳", basis: "活动强度处于持续变化状态" };
      }
      if (triplet.motion.state === "micro_motion") {
        return { label: "恢复", basis: "活动强度只剩轻微变化" };
      }
      return { label: "静息", basis: "活动强度趋于平稳" };
    case "feng_shui":
      if (triplet.motion.state === "fast_change") {
        return { label: "冲", basis: "活动强度正在快速变化" };
      }
      if (triplet.occupancy_density.state === "high") {
        return { label: "滞", basis: "充盈代理偏高" };
      }
      if (triplet.occupancy_density.state === "medium") {
        return { label: "聚", basis: "充盈代理居中" };
      }
      return { label: "散", basis: "充盈代理偏低" };
    case "psyche":
      if (triplet.status === "degraded" || triplet.sensor_confidence_cap < 0.55) {
        return { label: "漂浮", basis: "质量边界偏弱；不是人物心理判断" };
      }
      if (triplet.motion.state === "idle") {
        return { label: "安定", basis: "活动强度趋于平稳；不是人物情绪判断" };
      }
      if (triplet.motion.state === "fast_change") {
        return { label: "警觉", basis: "活动强度快速变化；不是人物情绪判断" };
      }
      return { label: "活跃", basis: "活动强度有轻微或持续变化" };
    case "soundscape":
      if (triplet.motion.state === "idle") {
        return { label: "静音", basis: "活动强度趋于平稳，对应较弱声景映射" };
      }
      if (triplet.motion.state === "fast_change") {
        return { label: "回响", basis: "活动强度快速变化，对应较强声景映射" };
      }
      return { label: "低鸣", basis: "活动强度仍在变化，对应连续声景映射" };
    case "skeptic":
      if (triplet.status === "degraded" || triplet.sensor_confidence_cap < 0.55) {
        return { label: "退后", basis: "质量降级或传感置信度上限较低" };
      }
      return { label: "观察", basis: "质量门已通过，仍检查冲突与越界解释" };
    case "fusion":
      if (triplet.motion.state === "fast_change") {
        return { label: "涌动", basis: "活动强度快速变化" };
      }
      if (triplet.occupancy_density.state === "high" || triplet.occupancy_density.state === "medium") {
        return { label: "聚拢", basis: "充盈代理处于中高状态" };
      }
      if (triplet.occupancy_density.state === "low") {
        return { label: "展开", basis: "充盈代理偏低" };
      }
      return { label: "静息", basis: "活动与充盈代理趋于平稳" };
  }
}

function reactionExplanation(
  role: VoiceRole,
  snapshot: SignalTriplet | null,
  reaction: AgentReaction,
  reading: VoiceReading,
): string {
  if (reading.source !== "pending") {
    if (reading.lifeInteraction) return reading.lifeInteraction.message;
    if (reading.assessment) return skepticReadingTextFromAssessment(reading.assessment);
    if (reading.presentation?.analysis) return reading.presentation.analysis;
    return readableAgentText(reading.text);
  }
  if (!snapshot) return reading.text;
  const motion = motionLabel(snapshot.motion.state);
  const occupancy = occupancyLabel(snapshot.occupancy_density.state);
  const depth = depthLabel(snapshot.depth_zone.state);
  switch (role) {
    case "architecture":
      return `充盈代理为${occupancy}，相对纵深${depth}；视觉上像空间边界正在${reaction.label}。`;
    case "biota":
      return `活动强度${motion}；视觉上像一段连续变化正在${reaction.label}，不是生命识别。`;
    case "feng_shui":
      return `活动强度${motion}，充盈代理为${occupancy}；视觉上像流动节奏正在${reaction.label}。`;
    case "psyche":
      return `活动强度${motion}；视觉上呈现为${reaction.label}，不是人物心理或情绪判断。`;
    case "soundscape":
      return `活动强度${motion}；声景映射随之${reaction.label}，不是现场录音。`;
    case "skeptic":
      return `质量为${qualityLabel(snapshot.status)}，置信上限${percent(snapshot.sensor_confidence_cap)}；先检查干扰与越界解释。`;
    case "fusion":
      return `活动${motion}、充盈${occupancy}、纵深${depth}；综合反应为${reaction.label}，置信不超过${percent(snapshot.sensor_confidence_cap)}。`;
  }
}

function skepticReadingTextFromAssessment(
  assessment: NonNullable<AgentChallenge["assessment"]>,
): string {
  return [
    `证据是否充分：${assessment.evidence_label}。`,
    `是否暂缓判断：${assessment.withhold_judgment ? "是" : "否"}。`,
    `原因：${safeVoiceText(assessment.rationale)}`,
    `下一步验证：${safeVoiceText(assessment.next_validation)}`,
  ].join("");
}

function contributionLabel(role: VoiceRole): string {
  return {
    architecture: "看见空间的形 · 收紧 / 展开 / 阻断",
    biota: "看见空间的息 · 静息 / 惊跳 / 恢复",
    feng_shui: "看见空间的流 · 聚 / 散 / 滞 / 冲",
    psyche: "看见空间的势 · 安定 / 活跃 / 警觉 / 漂浮",
    soundscape: "把共识翻译成：节奏 / 音高 / 远近 / 厚薄 / 同步",
    skeptic: "证据是否充分 · 是否暂缓判断 · 下一步如何验证",
    fusion: "以空间生命视角告诉你：现在的状态 · 希望如何与你互动",
  }[role];
}

function readableAgentText(text: string): string {
  const safe = safeVoiceText(text);
  const clauses = safe
    .split(/[;；]/)
    .map((clause) => clause.trim())
    .filter(Boolean);
  const suggestionIndex = clauses.findIndex((clause) => clause.startsWith("建议:"));
  if (suggestionIndex >= 1) {
    const statement = clauses[suggestionIndex - 1];
    const suggestion = clauses[suggestionIndex]?.replace(/^建议:/, "接下来");
    return `${statement}；${suggestion}。`;
  }
  return safe;
}

function continuityLabel(
  relation: NonNullable<AgentClaim["continuity"]>["relation"],
): string {
  return {
    initial: "首次分析",
    steady: "延续观察",
    intensified: "递进增强",
    eased: "递进缓和",
    shifted: "观点转折",
    quality_changed: "质量边界改变",
    recovered: "恢复分析",
    unknown: "暂停沿用",
  }[relation];
}

function liveCycleState(
  state: StreamState,
  cycle: CycleView | null,
  returned: number,
  fieldHasAdvanced: boolean,
): string {
  if (state.connection === "offline") {
    return "连接中断 · 保留最近一次封存观点";
  }
  if (state.stale) {
    return "证据已暂停 · 保留最近一次封存观点";
  }
  if (!cycle) {
    return "等待首个封存证据周期";
  }
  if (fieldHasAdvanced) {
    return `Agent 正在解释上一封存时刻 · ${String(returned).padStart(2, "0")}/07 个视角已返回`;
  }
  if (cycle.result) {
    return `本轮综合完成 · ${String(returned).padStart(2, "0")}/07 个视角已返回`;
  }
  if (returned > 0) {
    return `本轮更新中 · ${String(returned).padStart(2, "0")}/07 个视角已返回`;
  }
  return "新证据已封存 · 七个视角正在读取";
}
