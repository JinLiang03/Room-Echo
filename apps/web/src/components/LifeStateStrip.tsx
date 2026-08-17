import { LIFE_STATE_IDS, lifeStateDefinition } from "../lib/life-state";
import { AgentDigitField } from "./AgentDigitField";

/**
 * The seven expressive states of one digital life, shown as bodies rather
 * than labels. The copy stays in accessibility semantics so the visual strip
 * remains entirely numeric without losing the inference-field boundary.
 */
export function LifeStateStrip() {
  return (
    <div
      className="life-state-strip"
      role="group"
      aria-label="七种数字生命状态的视觉谱系；艺术化信号解释，非真实影像"
    >
      {LIFE_STATE_IDS.map((id) => {
        const state = lifeStateDefinition(id);
        return (
          <div
            key={id}
            className={`life-state-strip-body life-state-strip-body-${id}`}
          >
            <AgentDigitField
              compact
              role={state.role}
              seed={`life-state-strip-${id}`}
              label={`${state.label}状态的彩色数字身体；视觉隐喻，不是现场物体识别或相机影像`}
            />
          </div>
        );
      })}
    </div>
  );
}
