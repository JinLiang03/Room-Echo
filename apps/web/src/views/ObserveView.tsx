import { SignalTrendBand } from "../components/SignalTrendBand";
import { SignalHouseField } from "../components/SignalHouseField";
import { SignalSculpture } from "../components/SignalSculpture";
import { ResultCard } from "../components/ResultCard";
import { DigitSectionMark } from "../components/DigitSectionMark";
import { useStream } from "../lib/state";

export function ObserveView({ visual = "house" }: { now: number; visual?: "house" | "sculpture" }) {
  const { state } = useStream();
  const result = latestResult(state);
  const visible = state.stale ? null : state.triplet;

  return (
    <section className="observe-layout" aria-label="Observe 视图">
      <div className="observe-main-column">
        <div className="panel scene-panel" aria-label="实时信号场">
          <header className="scene-head">
            <div>
              <span className="scene-kicker">OBSERVE / SENSOR FIELD</span>
              <h2 className="digit-heading">
                <DigitSectionMark role="architecture" seed="observe-house" />
                <span>实时信号场</span>
              </h2>
            </div>
            <span className="scene-boundary">INFERENCE FIELD · NOT A CAMERA IMAGE</span>
          </header>
          {visual === "house" ? (
            <SignalHouseField
              triplet={state.triplet}
              result={result}
              stale={state.stale}
              reducedMotion={state.settings.reducedMotion}
              debug={state.settings.debug}
            />
          ) : (
            <SignalSculpture
              triplet={state.triplet}
              result={result}
              stale={state.stale}
              reducedMotion={state.settings.reducedMotion}
              debug={state.settings.debug}
            />
          )}
          <SignalTrendBand
            triplet={state.triplet}
            history={state.history}
            quality={state.quality}
            result={result}
            stale={state.stale}
          />
          <div className="scene-meta-strip" aria-label="信号场元数据">
            <span>source {state.session?.mode ?? state.sourceHealth?.source_mode ?? "—"}</span>
            <span>window {visible?.window_id ?? "—"}</span>
            <span>cap {visible ? visible.sensor_confidence_cap.toFixed(3) : "—"}</span>
            <span>refresh 4 Hz</span>
          </div>
        </div>
      </div>

      <aside className="observe-result-column">
        <ResultCard
          triplet={state.triplet}
          result={result}
          stale={state.stale}
        />
      </aside>
    </section>
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
