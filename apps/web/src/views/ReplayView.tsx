import { formatSeconds, shortHash } from "../lib/format";
import { useStream } from "../lib/state";
import type { ReplayBundleSummary } from "../lib/types";
import { DigitSectionMark } from "../components/DigitSectionMark";

const SPEEDS = [0.25, 0.5, 1, 2, 4];

export function ReplayView() {
  const { state, controls } = useStream();
  const replay = state.replay;
  const session = state.session;
  const readOnly = session?.read_only === true;

  return (
    <section className="replay-view" aria-label="Replay 视图">
      <h2 className="digit-heading">
        <DigitSectionMark role="soundscape" seed="replay-title" size="medium" />
        <span>回放 / Replay</span>
      </h2>
      <div className="replay-purpose" aria-label="回放说明">
        <div>
          <span className="eyebrow">REPLAY / SEALED SOURCE</span>
          <p>把已封存的数据包按原时间顺序重送给前端，用来复现实验、核对证据与 Agent 周期；它不会改写实时会话。</p>
        </div>
        <dl className="replay-purpose-kv">
          <div>
            <dt>输入</dt>
            <dd>已校验 bundle</dd>
          </div>
          <div>
            <dt>输出</dt>
            <dd>窗口 · 周期 · 证据</dd>
          </div>
          <div>
            <dt>用途</dt>
            <dd>复现 / 对照</dd>
          </div>
        </dl>
      </div>
      {replay.error && (
        <div className="banner banner-error" role="alert">
          {replay.error}
        </div>
      )}

      <div className="panel">
        <h3 className="digit-heading">
          <DigitSectionMark role="architecture" seed="replay-recordings" />
          <span>录制列表</span>
        </h3>
        <ul className="bundle-list">
          {replay.bundles.length === 0 && <li>正在加载或后端不可用…</li>}
          {replay.bundles.map((bundle) => (
            <BundleRow
              key={bundle.bundle_id}
              bundle={bundle}
              selected={replay.selected === bundle.bundle_id}
              verifying={replay.verifying === bundle.bundle_id}
              readOnly={readOnly}
              onSelect={() => void controls.start(bundle.bundle_id)}
            />
          ))}
        </ul>
      </div>

      {(session || replay.selected) && (
        <div className="panel">
          <h3 className="digit-heading">
            <DigitSectionMark role="feng_shui" seed="replay-controls" />
            <span>回放控制</span>
          </h3>
          {readOnly ? (
            <p className="replay-read-only" role="note">
              公网体验由系统自动循环播放；访客不能暂停、跳转或切换数据源。
            </p>
          ) : (
            <div className="transport" aria-label="回放控制">
              <button type="button" className="button" disabled={!session?.running} onClick={session?.paused ? controls.resume : controls.pause}>
                {session?.paused ? "播放" : "暂停"}
              </button>
              <button type="button" className="button" disabled={!session?.running} onClick={() => controls.step(10)}>
                单步 +10
              </button>
              <button type="button" className="button" disabled={!session?.running} onClick={() => controls.seek(0)}>
                回到起点
              </button>
              <span className="speed-group" role="group" aria-label="回放速度">
                {SPEEDS.map((speed) => (
                  <button
                    key={speed}
                    type="button"
                    className={`button button-small ${session?.rate === speed ? "button-active" : ""}`}
                    onClick={() => controls.rate(speed)}
                  >
                    {speed}×
                  </button>
                ))}
              </span>
            </div>
          )}
          <dl className="kv transport-stats">
            <div>
              <dt>position</dt>
              <dd>{formatSeconds(session?.position_s)}</dd>
            </div>
            <div>
              <dt>frames</dt>
              <dd>{session?.frames ?? 0}</dd>
            </div>
            <div>
              <dt>windows</dt>
              <dd>{session?.windows ?? 0}</dd>
            </div>
            <div>
              <dt>evidence seals</dt>
              <dd>{session?.evidence_seals ?? 0}</dd>
            </div>
            <div>
              <dt>recompute</dt>
              <dd>{session?.recompute ? "true" : "false"}</dd>
            </div>
          </dl>
        </div>
      )}

      <div className="panel">
        <h3 className="digit-heading">
          <DigitSectionMark role="fusion" seed="replay-cycles" />
          <span>周期标记</span>
        </h3>
        <ul className="marker-list">
          {state.council.order.length === 0 && <li>暂无周期标记。</li>}
          {[...state.council.order].reverse().map((cycleId) => (
            <li key={cycleId}>
              <code>{cycleId}</code>
              <span>{state.council.cycles[cycleId]?.result?.status ?? "running"}</span>
              <span title={state.council.cycles[cycleId]?.evidenceHash}>
                {shortHash(state.council.cycles[cycleId]?.evidenceHash)}
              </span>
            </li>
          ))}
        </ul>
      </div>

      <GroundTruthBanner selected={replay.selected} bundles={replay.bundles} />
    </section>
  );
}

function BundleRow({
  bundle,
  selected,
  verifying,
  readOnly,
  onSelect,
}: {
  bundle: ReplayBundleSummary;
  selected: boolean;
  verifying: boolean;
  readOnly: boolean;
  onSelect: () => void;
}) {
  return (
    <li className={`bundle-row ${selected ? "bundle-selected" : ""}`}>
      <div className="bundle-info">
        <span className="bundle-name">{bundle.bundle_id}</span>
        <span className={`state-badge ${bundle.verified ? "state-valid" : "state-error"}`}>
          {bundle.verified ? "verified" : "verify failed"}
        </span>
        <span>{bundle.manifest?.source_mode ?? "?"}</span>
        <span>
          {(bundle.raw_bytes / 1024).toFixed(0)} KB ·{" "}
          {bundle.manifest?.status ?? "?"}
        </span>
      </div>
      {!bundle.verified && bundle.errors.length > 0 && (
        <ul className="bundle-errors">
          {bundle.errors.map((error, index) => (
            <li key={`${index}-${error}`}>{error}</li>
          ))}
        </ul>
      )}
      <button
        type="button"
        className="button button-small"
        disabled={!bundle.verified || verifying || readOnly}
        onClick={onSelect}
      >
        {readOnly ? "自动播放" : verifying ? "加载中…" : selected ? "已选择" : "加载"}
      </button>
    </li>
  );
}

function GroundTruthBanner({
  selected,
  bundles,
}: {
  selected: string | null;
  bundles: ReplayBundleSummary[];
}) {
  const { state } = useStream();
  const bundle = bundles.find((item) => item.bundle_id === selected);
  const present = bundle?.manifest?.ground_truth_present ?? false;
  if (!bundle || !present) {
    return null;
  }
  const shown = state.settings.showGroundTruth;
  return (
    <div className="banner banner-info" role="note">
      {shown ? (
        <>
          <strong>评估模式:</strong> ground truth 已显示 — 仅用于评估,不进入 Agent。
        </>
      ) : (
        <>
          <strong>ground truth 已隐藏。</strong> 该录制包含标注数据,默认不显示。
          可在设置中开启“显示 ground truth”进入评估模式。
        </>
      )}
    </div>
  );
}
