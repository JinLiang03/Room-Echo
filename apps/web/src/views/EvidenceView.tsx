import { pct, shortHash } from "../lib/format";
import { useStream } from "../lib/state";
import { Sparkline } from "../components/Sparkline";
import { DigitSectionMark } from "../components/DigitSectionMark";
import { depthWeighted, occupancyWeighted } from "../lib/multimodal";

type TraceKind = "motion" | "occupancy" | "depth";

const TRACE_CONFIG: Record<
  TraceKind,
  { label: string; name: string; note: string; interpretation: string; stroke: string }
> = {
  motion: {
    label: "MOTION",
    name: "活动强度",
    note: "0 → 1 · 越高表示窗口变化越明显",
    interpretation: "无线变化代理，不等于速度或人数",
    stroke: "var(--coral)",
  },
  occupancy: {
    label: "OCCUPANCY PROXY",
    name: "空间占用代理",
    note: "low → high · 概率加权",
    interpretation: "只表示空间充盈度，不是人数统计",
    stroke: "var(--mint-strong)",
  },
  depth: {
    label: "DEPTH-ZONE PROXY",
    name: "相对纵深代理",
    note: "near → far · 相对层级",
    interpretation: "不表示米制距离或真实深度",
    stroke: "var(--butter-strong)",
  },
};

function traceValue(kind: TraceKind, item: ReturnType<typeof useStream>["state"]["history"][number]): number {
  if (kind === "motion") return item.motion.value;
  return kind === "occupancy" ? occupancyWeighted(item) : depthWeighted(item);
}

export function EvidenceView() {
  const { state } = useStream();
  const history = state.history;
  const result = latestResult(state);
  const quality = state.quality;
  const health = state.sourceHealth;
  const visible = state.stale ? null : state.triplet;

  return (
    <section className="evidence-view" aria-label="Evidence 视图">
      <h2 className="digit-heading">
        <DigitSectionMark role="architecture" seed="evidence-title" size="medium" />
        <span>Evidence</span>
      </h2>
      <div className="evidence-trace-panel panel">
        <div className="evidence-trace-intro">
          <div>
            <span className="eyebrow">SEALED WINDOWS / LEFT → RIGHT</span>
            <h3>三项信号轨迹</h3>
            <p>每个点代表一个 250ms 窗口；横轴从较早窗口走向最新窗口，纵轴统一为 0–1。</p>
          </div>
          <div className="evidence-trace-guide" aria-label="曲线阅读说明">
            <span>纵轴：代理强度</span>
            <span>横轴：时间顺序</span>
            <span>颜色：不同信号</span>
          </div>
        </div>
        <div className="evidence-traces">
          {(Object.keys(TRACE_CONFIG) as TraceKind[]).map((kind) => {
            const config = TRACE_CONFIG[kind];
            const values = history.map((item) => traceValue(kind, item));
            const current = visible ? traceValue(kind, visible) : null;
            return (
              <EvidenceTrace
                key={kind}
                config={config}
                values={values}
                current={current}
              />
            );
          })}
        </div>
      </div>

      <div className="evidence-grid">
        <div className="panel">
          <h3 className="digit-heading">
            <DigitSectionMark role="psyche" seed="evidence-quality" />
            <span>质量</span>
          </h3>
          <dl className="kv">
            <div>
              <dt>status</dt>
              <dd>{quality?.status ?? "—"}</dd>
            </div>
            <div>
              <dt>packet coverage</dt>
              <dd>{quality ? pct(quality.packet_coverage, 1) : "—"}</dd>
            </div>
            <div>
              <dt>paired coverage</dt>
              <dd>{quality ? pct(quality.paired_coverage, 1) : "—"}</dd>
            </div>
            <div>
              <dt>flags</dt>
              <dd>{quality?.quality_flags?.join(", ") || "—"}</dd>
            </div>
          </dl>
        </div>
        <div className="panel">
          <h3 className="digit-heading">
            <DigitSectionMark role="architecture" seed="evidence-topology" />
            <span>拓扑与标定</span>
          </h3>
          <dl className="kv">
            <div>
              <dt>links</dt>
              <dd>{health?.link_ids?.join(", ") ?? "—"}</dd>
            </div>
            <div>
              <dt>topology</dt>
              <dd>{shortHash(health?.topology_hash)}</dd>
            </div>
            <div>
              <dt>calibration</dt>
              <dd>{health?.calibration_profile_id ?? "—"}</dd>
            </div>
            <div>
              <dt>channel</dt>
              <dd>
                {health?.channel ?? "—"}
                {health?.bandwidth_mhz ? ` / ${health.bandwidth_mhz}MHz` : ""}
              </dd>
            </div>
            <div>
              <dt>recompute</dt>
              <dd>{health?.recompute ? "true" : "false"}</dd>
            </div>
          </dl>
        </div>
        <div className="panel">
          <h3 className="digit-heading">
            <DigitSectionMark role="fusion" seed="evidence-provenance" />
            <span>Provenance</span>
          </h3>
          {result ? (
            <dl className="kv">
              <div>
                <dt>features</dt>
                <dd>{result.provenance.features_version}</dd>
              </div>
              <div>
                <dt>policy</dt>
                <dd>{result.provenance.policy_version}</dd>
              </div>
              <div>
                <dt>evidence hash</dt>
                <dd>{shortHash(result.evidence_hash, 20)}</dd>
              </div>
              <div>
                <dt>models</dt>
                <dd>{Object.entries(result.provenance.models ?? {}).map(([role, model]) => `${role}:${model}`).join(", ") || "—"}</dd>
              </div>
            </dl>
          ) : (
            <p>暂无已提交的 Council 结果。</p>
          )}
          <p className="chart-note">
            raw CSI 与 ground truth 不会发送到浏览器;这里只展示密封摘要与来源。
          </p>
        </div>
      </div>
    </section>
  );
}

function EvidenceTrace({
  config,
  values,
  current,
}: {
  config: (typeof TRACE_CONFIG)[TraceKind];
  values: number[];
  current: number | null;
}) {
  return (
    <article className="evidence-trace" aria-label={`${config.name}证据曲线`}>
      <header className="evidence-trace-head">
        <div>
          <span className="evidence-trace-label" style={{ color: config.stroke }}>
            {config.label}
          </span>
          <strong>{config.name}</strong>
        </div>
        <div className="evidence-trace-current">
          <span>最新窗口</span>
          <strong style={{ color: config.stroke }}>
            {current === null ? "—" : current.toFixed(2)}
          </strong>
        </div>
      </header>
      <div className="evidence-chart-frame">
        <div className="evidence-y-axis" aria-hidden="true">
          <span>1.0</span>
          <span>0.5</span>
          <span>0</span>
        </div>
        <div className="evidence-chart-plot">
          <Sparkline
            values={values}
            width={640}
            height={74}
            stroke={config.stroke}
            ariaLabel={`${config.name}证据轨迹，横轴为时间顺序，纵轴为 0 到 1 的代理强度`}
          />
        </div>
      </div>
      <div className="evidence-x-axis" aria-hidden="true">
        <span>较早窗口</span>
        <span>最新窗口 →</span>
      </div>
      <p>
        {config.note} · {config.interpretation}
      </p>
    </article>
  );
}

function latestResult(state: ReturnType<typeof useStream>["state"]) {
  const order = state.council.order;
  for (let index = order.length - 1; index >= 0; index -= 1) {
    const cycle = state.council.cycles[order[index]];
    if (cycle?.result) {
      return cycle.result;
    }
  }
  return null;
}
