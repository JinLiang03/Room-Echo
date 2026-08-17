import type { CouncilResult, SignalTriplet } from "../lib/types";
import { HISTORY_LIMIT } from "../lib/types";
import { councilStatusLabel, num, pct, stateLabel } from "../lib/format";
import { Sparkline } from "./Sparkline";
import { DigitSectionMark } from "./DigitSectionMark";

export type CardState = "valid" | "degraded" | "unknown" | "stale";
export type SignalKind = "motion" | "occupancy" | "depth";

interface Props {
  kind: SignalKind;
  triplet: SignalTriplet | null;
  result: CouncilResult | null;
  history?: SignalTriplet[];
  stale: boolean;
  now: number;
  lastEventAt: number | null;
}

const TITLES: Record<SignalKind, string> = {
  motion: "活动强度 motion_intensity",
  occupancy: "占用/遮挡密度代理 occupancy_density_proxy",
  depth: "空间纵深代理 depth_zone_proxy",
};

const NOTES: Record<SignalKind, string> = {
  motion: "0–1 连续量 · 相对运动强度",
  occupancy: "low/medium/high 概率 · 非人数",
  depth: "near/mid/far 概率 · 非米制距离",
};

const MARK_ROLES: Record<SignalKind, string> = {
  motion: "soundscape",
  occupancy: "biota",
  depth: "feng_shui",
};

function cardState(triplet: SignalTriplet | null, stale: boolean): CardState {
  if (stale || triplet === null) {
    return "stale";
  }
  if (triplet.status === "insufficient_signal" || triplet.status === "uncalibrated") {
    return "unknown";
  }
  if (triplet.status === "degraded") {
    return "degraded";
  }
  return "valid";
}

function signalConfidence(
  kind: SignalKind,
  triplet: SignalTriplet | null,
): number | null {
  if (!triplet) {
    return null;
  }
  if (kind === "motion") {
    return triplet.motion.confidence;
  }
  if (kind === "occupancy") {
    return triplet.occupancy_density.confidence;
  }
  return triplet.depth_zone.confidence;
}

function signalState(kind: SignalKind, triplet: SignalTriplet): string {
  if (kind === "motion") {
    return triplet.motion.state;
  }
  if (kind === "occupancy") {
    return triplet.occupancy_density.state;
  }
  return triplet.depth_zone.state;
}

function signalSeries(
  history: SignalTriplet[],
  current: SignalTriplet,
): number[] {
  const source = history.length > 0 ? history : [current];
  return source
    .slice(-HISTORY_LIMIT)
    .map((item) => item.motion.value)
    .filter(Number.isFinite);
}

function ProbabilityBars({ kind, triplet }: { kind: SignalKind; triplet: SignalTriplet }) {
  const rows = probabilityRows(kind, triplet);
  return (
    <div className="prob-bars" aria-label={`${kind} 概率分布`}>
      {rows.map(({ label, value }) => (
        <div key={label} className="prob-row">
          <span className="prob-label">{label}</span>
          <div className="prob-track">
            <div
              className={`prob-fill prob-${label}`}
              style={{ width: `${value * 100}%` }}
            />
          </div>
          <span className="prob-value">{pct(value, 1)}</span>
        </div>
      ))}
    </div>
  );
}

function probabilityRows(
  kind: SignalKind,
  triplet: SignalTriplet,
): Array<{ label: string; value: number }> {
  if (kind === "occupancy") {
    const probabilities = triplet.occupancy_density.probabilities;
    return (["low", "medium", "high", "unknown"] as const).map((label) => ({
      label,
      value: probabilities[label],
    }));
  }
  const probabilities = triplet.depth_zone.probabilities;
  return (["near", "mid", "far", "unknown"] as const).map((label) => ({
    label,
    value: probabilities[label],
  }));
}

export function SignalCard({
  kind,
  triplet,
  result,
  history = [],
  stale,
  now,
  lastEventAt,
}: Props) {
  const state = cardState(triplet, stale);
  const visible = stale ? null : triplet;
  const confidence = signalConfidence(kind, visible);
  const freshness =
    lastEventAt === null
      ? "无数据"
      : now - lastEventAt < 3000
        ? "实时"
        : `${((now - lastEventAt) / 1000).toFixed(1)}s 前`;

  return (
    <article className={`signal-card card-state-${state}`} aria-label={TITLES[kind]}>
      <header className="signal-card-head">
        <h3 className="digit-heading">
          <DigitSectionMark role={MARK_ROLES[kind]} seed={`signal-${kind}`} />
          <span>{TITLES[kind]}</span>
        </h3>
        <span className={`state-badge state-${state}`}>{stateLabel(state)}</span>
      </header>
      <div className="signal-value">
        {visible ? (
          <>
            <span className="signal-number">
              {kind === "motion" ? num(visible.motion.value) : stateLabel(signalState(kind, visible))}
            </span>
            {kind !== "motion" && (
              <span className="signal-state">{stateLabel(signalState(kind, visible))}</span>
            )}
          </>
        ) : (
          <span className="signal-number">—</span>
        )}
      </div>
      {visible ? (
        kind === "motion" ? (
          <Sparkline
            values={signalSeries(history, visible)}
            ariaLabel="运动强度变化曲线"
            stroke={state === "unknown" ? "var(--unknown)" : "var(--accent)"}
          />
        ) : (
          <ProbabilityBars kind={kind} triplet={visible} />
        )
      ) : (
        <Sparkline values={[]} ariaLabel="无数据曲线" />
      )}
      <dl className="scores">
        <div>
          <dt>测量质量</dt>
          <dd>
            {confidence === null ? "—" : pct(confidence)}
            {visible && visible.status !== "ok" ? ` (${visible.status})` : ""}
          </dd>
        </div>
        <div>
          <dt>模型支持</dt>
          <dd>{result ? pct(result.model_support) : "—"}</dd>
        </div>
        <div>
          <dt>推理一致性</dt>
          <dd>
            {result
              ? `${result.interpretation_agreement.supporting} / ${result.interpretation_agreement.participants}`
              : "—"}
          </dd>
        </div>
      </dl>
      <footer className="signal-foot">
        <span>{NOTES[kind]}</span>
        <span>状态 {councilStatusLabel(result)}</span>
        <span>{freshness}</span>
      </footer>
    </article>
  );
}
