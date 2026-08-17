import { useState } from "react";
import { DigitSectionMark } from "../components/DigitSectionMark";
import { lifeStateDefinition } from "../lib/life-state";
import {
  deleteLifeMemory,
  readLifeMemories,
  type LifeMemory,
} from "../lib/memories";
import { navigate, routeParams } from "../lib/router";
import { useStream } from "../lib/state";
import { ReplayView } from "./ReplayView";

const TIME_FORMAT = new Intl.DateTimeFormat("zh-CN", {
  month: "2-digit",
  day: "2-digit",
  hour: "2-digit",
  minute: "2-digit",
});

const QUICK_REPLAY_BUNDLE = "demo_2min";

export function MemoryView() {
  const { state, controls } = useStream();
  const [memories, setMemories] = useState(readLifeMemories);
  const [replayPending, setReplayPending] = useState(false);
  const audit = state.settings.debug || routeParams().get("audit") === "1";

  const quickReplay = async () => {
    if (replayPending) return;
    setReplayPending(true);
    const bundleId = state.replay.selected ?? QUICK_REPLAY_BUNDLE;
    const sameReplayRunning =
      state.session?.running === true &&
      state.session.mode === "replay" &&
      state.session.bundle_id === bundleId;
    if (state.session?.running && !sameReplayRunning) {
      await controls.stop();
    }
    await controls.start(bundleId);
    navigate("home");
  };

  return (
    <section className="memory-view" aria-label="数字生命记忆">
      <h2 className="visually-hidden">记忆</h2>
      <div className="memory-toolbar">
        <small className="memory-boundary">本机视觉书签 · 非场景识别</small>
        <button
          type="button"
          className="memory-replay-button"
          aria-label="快速重播演示"
          aria-busy={replayPending}
          disabled={replayPending}
          onClick={() => void quickReplay()}
        >
          <span aria-hidden="true">↻</span>
          <span>{replayPending ? "加载中" : "重播"}</span>
        </button>
      </div>
      <div className="memory-field" aria-live="polite">
        {memories.length === 0 ? (
          <div className="memory-empty" aria-label="还没有保存的本机视觉记忆">
            <DigitSectionMark role="fusion" seed="empty-memory" size="medium" />
          </div>
        ) : (
          memories.map((memory) => (
            <MemoryGlyph
              key={memory.id}
              memory={memory}
              onDelete={() => setMemories(deleteLifeMemory(memory.id))}
            />
          ))
        )}
      </div>
      {audit && (
        <details className="audit-layer" open>
          <summary>评委模式 · 技术回放</summary>
          <ReplayView />
        </details>
      )}
    </section>
  );
}

function MemoryGlyph({
  memory,
  onDelete,
}: {
  memory: LifeMemory;
  onDelete: () => void;
}) {
  const definition = lifeStateDefinition(memory.lifeState);
  const createdAt = new Date(memory.createdAt);
  return (
    <article className="memory-glyph" aria-label={`${definition.label}状态的本机视觉记忆`}>
      <DigitSectionMark
        role={definition.role}
        seed={memory.signature}
        size="medium"
      />
      <span>{definition.label}</span>
      <time dateTime={memory.createdAt}>
        {Number.isNaN(createdAt.getTime()) ? "—" : TIME_FORMAT.format(createdAt)}
      </time>
      <button type="button" onClick={onDelete} aria-label={`删除${definition.label}记忆`}>
        ×
      </button>
    </article>
  );
}
