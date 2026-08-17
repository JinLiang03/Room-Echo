import { useEffect, useState } from "react";
import { useStream } from "../lib/state";
import { useSoundscape } from "../lib/audio-context";
import type { Settings } from "../lib/types";
import { DigitSectionMark } from "../components/DigitSectionMark";

export function SettingsPanel() {
  const { state, controls } = useStream();
  const engine = useSoundscape();
  const [audio, setAudio] = useState(() => engine?.stats ?? null);
  const settings = state.settings;

  useEffect(() => {
    if (!engine) {
      return;
    }
    const refresh = () => setAudio(engine.stats);
    refresh();
    return engine.subscribe(refresh);
  }, [engine]);

  const patch = (change: Partial<Settings>) => {
    const next = { ...settings, ...change };
    controls.setSettings(next);
  };

  const exportData = () => {
    const blob = new Blob([JSON.stringify(state, null, 2)], {
      type: "application/json",
    });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = "wifi-spatial-council-state.json";
    anchor.click();
    URL.revokeObjectURL(url);
  };

  return (
    <section className="settings-view" aria-label="设置">
      <h2 className="digit-heading">
        <DigitSectionMark role="feng_shui" seed="settings-title" size="medium" />
        <span>设置</span>
      </h2>
      <div className="panel">
        <h3 className="digit-heading">
          <DigitSectionMark role="soundscape" seed="settings-audio" />
          <span>声音与动画(声景 Phase 09)</span>
        </h3>
        <div className="audio-row">
          <span className="audio-status">
            {audio === null
              ? "Web Audio 不可用"
              : audio.enabled
                ? audio.muted
                  ? "已启用 · 静音"
                  : audio.active
                    ? "运行中"
                    : "已启用 · 等待信号"
                : "未启用(需一次点击手势)"}
          </span>
          <button
            type="button"
            className="button button-small"
            disabled={audio?.enabled === true}
            onClick={() => engine?.enable()}
          >
            启用声景
          </button>
        </div>
        <p className="chart-note">
          motion→tempo · occupancy→filter/harmonics · depth→stereo width ·
          quality→clarity;默认静音,不自动播放,无警报音。
        </p>
        <Toggle
          label="全局静音"
          checked={settings.muted}
          onChange={(muted) => {
            patch({ muted });
            engine?.setMuted(muted);
          }}
        />
        <Toggle
          label="减少动态(prefers-reduced-motion)"
          checked={settings.reducedMotion}
          onChange={(reducedMotion) => patch({ reducedMotion })}
        />
      </div>
      <div className="panel">
        <h3 className="digit-heading">
          <DigitSectionMark role="psyche" seed="settings-display" />
          <span>可访问性与显示</span>
        </h3>
        <Toggle
          label="高对比度配色"
          checked={settings.highContrast}
          onChange={(highContrast) => patch({ highContrast })}
        />
        <Toggle
          label="显示 ground truth(评估模式)"
          checked={settings.showGroundTruth}
          onChange={(showGroundTruth) => patch({ showGroundTruth })}
        />
        <Toggle
          label="调试信息(sequence/丢弃/连接)"
          checked={settings.debug}
          onChange={(debug) => patch({ debug })}
        />
      </div>
      <div className="panel">
        <h3 className="digit-heading">
          <DigitSectionMark role="architecture" seed="settings-data" />
          <span>数据</span>
        </h3>
        <button type="button" className="button" onClick={exportData}>
          导出当前状态 JSON
        </button>
        <p className="chart-note">
          导出包含当前快照与周期摘要,不含 raw CSI、ground truth 或凭据。
        </p>
      </div>
      {settings.debug && (
        <div className="panel" aria-label="调试信息">
          <h3 className="digit-heading">
            <DigitSectionMark role="skeptic" seed="settings-debug" />
            <span>Debug</span>
          </h3>
          <dl className="kv">
            <div>
              <dt>connection</dt>
              <dd>{state.connection}</dd>
            </div>
            <div>
              <dt>sequence</dt>
              <dd>{state.sequence}</dd>
            </div>
            <div>
              <dt>applied</dt>
              <dd>{state.applied}</dd>
            </div>
            <div>
              <dt>dropped(out-of-order)</dt>
              <dd>{state.dropped}</dd>
            </div>
            <div>
              <dt>history</dt>
              <dd>{state.history.length}</dd>
            </div>
          </dl>
        </div>
      )}
    </section>
  );
}

function Toggle({
  label,
  checked,
  onChange,
}: {
  label: string;
  checked: boolean;
  onChange: (value: boolean) => void;
}) {
  return (
    <label className="toggle-row">
      <input
        type="checkbox"
        checked={checked}
        onChange={(event) => onChange(event.target.checked)}
      />
      <span>{label}</span>
    </label>
  );
}
