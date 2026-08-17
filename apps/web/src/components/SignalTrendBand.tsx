import type { CouncilResult, QualityView, SignalTriplet } from "../lib/types";
import { HISTORY_LIMIT } from "../lib/types";
import { depthWeighted, measurementQuality, occupancyWeighted } from "../lib/multimodal";
import { num, pct, stateLabel } from "../lib/format";
import { Sparkline } from "./Sparkline";

type TrendKind = "motion" | "occupancy" | "depth";

interface Props {
  triplet: SignalTriplet | null;
  history: SignalTriplet[];
  quality: QualityView | null;
  result: CouncilResult | null;
  stale: boolean;
}

const TREND_CONFIG: Record<
  TrendKind,
  { label: string; name: string; accent: string; note: string }
> = {
  motion: {
    label: "MOTION",
    name: "活动强度",
    accent: "var(--coral)",
    note: "连续代理量 · 0–1",
  },
  occupancy: {
    label: "OCCUPANCY PROXY",
    name: "遮挡 / 空间占用代理",
    accent: "var(--mint-strong)",
    note: "概率加权 · 非人数",
  },
  depth: {
    label: "DEPTH-ZONE PROXY",
    name: "相对纵深代理",
    accent: "var(--butter-strong)",
    note: "near / mid / far · 非米制距离",
  },
};

function trendValue(kind: TrendKind, triplet: SignalTriplet): number {
  if (kind === "motion") {
    return triplet.motion.value;
  }
  return kind === "occupancy" ? occupancyWeighted(triplet) : depthWeighted(triplet);
}

function trendState(kind: TrendKind, triplet: SignalTriplet): string {
  if (kind === "motion") {
    return triplet.motion.state;
  }
  return kind === "occupancy"
    ? triplet.occupancy_density.state
    : triplet.depth_zone.state;
}

function trendConfidence(kind: TrendKind, triplet: SignalTriplet): number {
  if (kind === "motion") {
    return triplet.motion.confidence;
  }
  return kind === "occupancy"
    ? triplet.occupancy_density.confidence
    : triplet.depth_zone.confidence;
}

export function SignalTrendBand({ triplet, history, quality, result, stale }: Props) {
  const visible = stale ? null : triplet;
  const historyWindow = visible ? history.slice(-HISTORY_LIMIT) : [];
  const qualityValue = visible ? measurementQuality(visible) : null;
  const qualityStatus = quality?.status ?? (visible?.status ?? "unknown");
  const agreement = result
    ? `${result.interpretation_agreement.supporting}/${result.interpretation_agreement.participants}`
    : "—";

  return (
    <section className="signal-trend-band" aria-label="三项实时信号趋势">
      <header className="trend-band-head">
        <div>
          <span className="trend-band-kicker">SIGNAL TRENDS / 4 HZ</span>
          <h3>实时信号走势</h3>
        </div>
        <div className="trend-band-health">
          <span>QUALITY</span>
          <strong>{qualityValue === null ? "—" : pct(qualityValue, 1)}</strong>
          <small>{stateLabel(qualityStatus)}</small>
        </div>
      </header>
      <div className="trend-lanes">
        {(Object.keys(TREND_CONFIG) as TrendKind[]).map((kind) => {
          const config = TREND_CONFIG[kind];
          const values = historyWindow.map((item) => trendValue(kind, item));
          const value = visible ? trendValue(kind, visible) : null;
          const confidence = visible ? trendConfidence(kind, visible) : null;
          return (
            <article className="trend-lane" key={kind} aria-label={config.name}>
              <div className="trend-lane-copy">
                <span className="trend-lane-label" style={{ color: config.accent }}>
                  {config.label}
                </span>
                <strong>{config.name}</strong>
                <small>{config.note}</small>
              </div>
              <Sparkline
                values={values}
                width={560}
                height={54}
                stroke={config.accent}
                ariaLabel={`${config.name}实时趋势`}
              />
              <div className="trend-lane-value">
                <strong style={{ color: config.accent }}>
                  {value === null ? "—" : num(value)}
                </strong>
                <span>{visible ? stateLabel(trendState(kind, visible)) : "unknown"}</span>
                <small>
                  {confidence === null ? "confidence —" : `confidence ${pct(confidence, 0)}`}
                </small>
              </div>
            </article>
          );
        })}
      </div>
      <footer className="trend-band-foot">
        <span>sensor quality 与 Agent agreement 分开</span>
        <span>agreement {agreement}</span>
        <span>趋势只表示已接收窗口，不是影像</span>
      </footer>
    </section>
  );
}
