import { useState } from "react";
import { StreamContext, type StreamControls } from "../lib/state";
import { buildStoryState, STORY_SCENARIOS, type StoryScenario } from "../lib/story";
import { CouncilView } from "./CouncilView";
import { EvidenceView } from "./EvidenceView";
import { ObserveView } from "./ObserveView";
import { DigitSectionMark } from "../components/DigitSectionMark";

const STORY_CONTROLS: StreamControls = {
  pause: () => undefined,
  resume: () => undefined,
  step: () => undefined,
  seek: () => undefined,
  rate: () => undefined,
  record: () => undefined,
  start: async () => undefined,
  stop: async () => undefined,
  loadBundles: async () => undefined,
  setSettings: () => undefined,
};

export function StoryView() {
  const [scenario, setScenario] = useState<StoryScenario>("moving");
  const state = buildStoryState(scenario);

  return (
    <StreamContext.Provider value={{ state, controls: STORY_CONTROLS }}>
      <section className="story-view" aria-label="Story 演示路线">
        <h2 className="digit-heading">
          <DigitSectionMark role="biota" seed="story-title" size="medium" />
          <span>Story — 固定状态演示</span>
        </h2>
        <div className="scenario-picker" role="group" aria-label="选择场景">
          {STORY_SCENARIOS.map((name) => (
            <button
              key={name}
              type="button"
              className={`button button-small ${scenario === name ? "button-active" : ""}`}
              onClick={() => setScenario(name)}
            >
              {name}
            </button>
          ))}
        </div>
        <p className="chart-note">
          使用固定 Mock 状态快速检查所有视觉状态;实时视图请连后端后看 Observe。
        </p>
        <ObserveView now={Date.now()} visual="sculpture" />
        <CouncilView />
        <EvidenceView />
      </section>
    </StreamContext.Provider>
  );
}
