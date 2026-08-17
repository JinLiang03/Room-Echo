import { DigitSectionMark } from "../components/DigitSectionMark";
import { routeParams } from "../lib/router";
import { useStream } from "../lib/state";
import type { StreamState } from "../lib/types";
import { CouncilView } from "./CouncilView";
import { EvidenceView } from "./EvidenceView";

export function WhyView({ evidenceFirst = false }: { evidenceFirst?: boolean }) {
  const { state } = useStream();
  const newest = newestCycle(state);
  const latest = latestInterpretableCycle(state) ?? newest;
  const isReviewingPrevious = Boolean(
    latest && newest && latest.cycleId !== newest.cycleId,
  );
  const audit = state.settings.debug || routeParams().get("audit") === "1";
  const showEvidence = evidenceFirst || routeParams().get("section") === "evidence";
  const challenge = latest?.challenges.find((item) => item.status === "open") ?? latest?.challenges[0];

  return (
    <section className="why-view" aria-label="为什么">
      <div className="why-summary" aria-live="polite">
        <DigitSectionMark
          role="fusion"
          seed={latest?.result?.cycle_id ?? "why-waiting"}
          size="medium"
        />
        <p>{latest?.result?.headline ?? "等待新的证据周期"}</p>
        {isReviewingPrevious && (
          <small>此刻证据不足 · 回看最近一次可解释周期</small>
        )}
        {challenge && <small>主要质疑 · {challenge.statement}</small>}
      </div>
      <section className="why-public-explanation" aria-label="Room Echo 的判断边界">
        <p>
          前台只有 Room Echo 一个 Agent。内部审议只用于反证、质量门与审计，
          不会用角色数量抬高传感置信度。
        </p>
        {latest?.result && (
          <dl>
            <div>
              <dt>本轮解释</dt>
              <dd>{Math.round(latest.result.display_confidence * 100)}%</dd>
            </div>
            <div>
              <dt>传感上限</dt>
              <dd>{Math.round(latest.result.sensor_confidence_cap * 100)}%</dd>
            </div>
          </dl>
        )}
      </section>
      {audit && (
        <details className="why-layer" open>
          <summary>内部审议记录</summary>
          <CouncilView />
        </details>
      )}
      {(showEvidence || audit) && <details className="why-layer" open>
        <summary>证据摘要</summary>
        <EvidenceView />
      </details>}
    </section>
  );
}

function newestCycle(state: StreamState) {
  for (let index = state.council.order.length - 1; index >= 0; index -= 1) {
    const cycle = state.council.cycles[state.council.order[index]];
    if (cycle) return cycle;
  }
  return null;
}

function latestInterpretableCycle(state: StreamState) {
  for (let index = state.council.order.length - 1; index >= 0; index -= 1) {
    const cycle = state.council.cycles[state.council.order[index]];
    if (cycle?.result && cycle.result.status !== "unavailable") return cycle;
  }
  return null;
}
