import { councilStatusLabel, pct, shortHash } from "../lib/format";
import type { CouncilResult, SignalTriplet } from "../lib/types";
import { DigitSectionMark } from "./DigitSectionMark";

interface Props {
  triplet: SignalTriplet | null;
  result: CouncilResult | null;
  stale: boolean;
}

export function ResultCard({ triplet, result, stale }: Props) {
  const visible = stale ? null : triplet;
  const measurementQuality = visible
    ? Math.min(
        visible.motion.confidence,
        visible.occupancy_density.confidence,
        visible.depth_zone.confidence,
      )
    : 0;
  const resultSensorCap = result?.sensor_confidence_cap ?? visible?.sensor_confidence_cap;

  return (
    <article className="result-card panel" aria-label="结果卡">
      <div className="result-watermark">INFERENCE FIELD — NOT A CAMERA IMAGE</div>
      <p className={`conclusion-status status-${result?.status ?? "none"}`}>
        {councilStatusLabel(result)}
      </p>
      <h2 className="result-headline digit-heading">
        <DigitSectionMark role="fusion" seed="result-headline" size="medium" />
        <span>{result?.headline ?? "讨论不可用"}</span>
      </h2>
      <p className="result-summary">
        {result?.summary ?? "Agent 未产生结果;三信号持续显示。"}
      </p>

      <h3 className="digit-heading">
        <DigitSectionMark role="soundscape" seed="result-signals" />
        <span>三信号</span>
      </h3>
      <dl className="kv">
        <div>
          <dt>motion</dt>
          <dd>
            {visible ? `${visible.motion.value.toFixed(2)} · ${visible.motion.state}` : "—"}
          </dd>
        </div>
        <div>
          <dt>occupancy</dt>
          <dd>
            {visible
              ? `${visible.occupancy_density.state} · ${pct(visible.occupancy_density.confidence)}`
              : "—"}
          </dd>
        </div>
        <div>
          <dt>depth</dt>
          <dd>
            {visible ? `${visible.depth_zone.state} · ${pct(visible.depth_zone.confidence)}` : "—"}
          </dd>
        </div>
      </dl>

      <h3 className="digit-heading">
        <DigitSectionMark role="skeptic" seed="result-confidence-boundary" />
        <span>置信度边界</span>
      </h3>
      <dl className="confidence-separation" aria-label="传感器与结论置信度边界">
        <div>
          <dt>sensor cap</dt>
          <dd>{resultSensorCap !== undefined ? resultSensorCap.toFixed(3) : "—"}</dd>
        </div>
        <div>
          <dt>model support</dt>
          <dd>{result ? pct(result.model_support, 1) : "—"}</dd>
        </div>
        <div>
          <dt>final claim</dt>
          <dd>{result ? pct(result.display_confidence, 1) : "—"}</dd>
        </div>
      </dl>

      <h3 className="digit-heading">
        <DigitSectionMark role="psyche" seed="result-quality" />
        <span>三个质量维度</span>
      </h3>
      <dl className="kv">
        <div>
          <dt>测量质量</dt>
          <dd>
            {pct(measurementQuality)}
            {visible && visible.status !== "ok" ? ` (${visible.status})` : ""}
          </dd>
        </div>
        <div>
          <dt>模型支持</dt>
          <dd>{result ? pct(result.model_support) : "—"}</dd>
        </div>
        <div>
          <dt>推理一致性</dt>
          <dd>
            {result
              ? `${result.interpretation_agreement.supporting} 一致 / ${result.interpretation_agreement.contradicting} 分歧 / ${result.interpretation_agreement.unresolved_challenges} 未解决`
              : "—"}
          </dd>
        </div>
      </dl>

      <h3 className="digit-heading">
        <DigitSectionMark role="biota" seed="result-alternatives" />
        <span>替代解释</span>
      </h3>
      <ul className="result-list">
        {(result?.alternatives?.length ? result.alternatives : ["无"]).map(
          (item, index) => (
            <li key={`${index}-${item}`}>{item}</li>
          ),
        )}
      </ul>

      <h3 className="digit-heading">
        <DigitSectionMark role="skeptic" seed="result-limitations" />
        <span>限制</span>
      </h3>
      <ul className="result-list">
        {(result?.limitations?.length
          ? result.limitations
          : ["代理信号,非影像、非人数、非米制距离"]
        ).map((item, index) => (
          <li key={`${index}-${item}`}>{item}</li>
        ))}
      </ul>

      <h3 className="digit-heading">
        <DigitSectionMark role="architecture" seed="result-provenance" />
        <span>版本与哈希</span>
      </h3>
      <dl className="kv">
        <div>
          <dt>evidence hash</dt>
          <dd>{shortHash(result?.evidence_hash, 20)}</dd>
        </div>
        <div>
          <dt>features</dt>
          <dd>{result?.provenance.features_version ?? "—"}</dd>
        </div>
        <div>
          <dt>policy</dt>
          <dd>{result?.provenance.policy_version ?? "—"}</dd>
        </div>
        <div>
          <dt>mapping</dt>
          <dd>multimodal-v1</dd>
        </div>
      </dl>
    </article>
  );
}
