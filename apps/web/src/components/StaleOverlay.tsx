interface Props {
  reason: "offline" | "paused" | "finished";
}

const COPY: Record<Props["reason"], string> = {
  offline: "连接已断开 — 数据暂停,恢复前不假装实时",
  paused: "回放已暂停 — 显示暂停时的数据",
  finished: "回放已结束 — 显示最后封存的结果",
};

export function StaleOverlay({ reason }: Props) {
  return (
    <div className="stale-overlay" role="status" aria-live="polite">
      <span className="stale-dot" aria-hidden="true" />
      {COPY[reason]}
    </div>
  );
}
