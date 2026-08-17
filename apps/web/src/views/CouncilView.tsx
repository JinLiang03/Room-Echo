import { shortHash } from "../lib/format";
import { personaFor } from "../lib/personas";
import { useStream } from "../lib/state";
import type { AgentChallenge, AgentClaim, PolicyRejection } from "../lib/types";
import { PersonaMark } from "../components/PersonaMark";
import { AgentDigitField } from "../components/AgentDigitField";
import { DigitSectionMark } from "../components/DigitSectionMark";

export function CouncilView() {
  const { state } = useStream();
  const cycles = [...state.council.order].reverse();

  if (state.council.discussionUnavailable && cycles.length === 0) {
    return (
      <section className="panel" aria-label="Council 视图">
        <h2 className="digit-heading">
          <DigitSectionMark role="skeptic" seed="council-unavailable" />
          <span>讨论不可用</span>
        </h2>
        <p>
          当前没有 Agent 周期结果。三信号持续显示;当证据封存且 Council
          完成后这里会按周期展示主张、挑战与最终结论。
        </p>
      </section>
    );
  }

  return (
    <section className="council-view" aria-label="Council 视图">
      <header className="council-intro">
        <div>
          <h2 className="digit-heading">
            <DigitSectionMark role="fusion" seed="council-title" size="medium" />
            <span>同一数字生命的完整审议记录</span>
          </h2>
          <p>七种视角只改变解释，不改写测量值与置信度上限。</p>
        </div>
        <p className="council-reading-guide">
          默认只展开最新一轮审议；较早周期保留在下方，可按需展开查看完整证据链。
        </p>
      </header>
      {cycles.length === 0 ? (
        <p>暂无周期。</p>
      ) : (
        <>
          {cycles[0] && state.council.cycles[cycles[0]] && (
            <CycleCard cycle={state.council.cycles[cycles[0]]} />
          )}
          {cycles.length > 1 && (
            <details className="older-cycles">
              <summary>较早周期 · {cycles.length - 1} 轮</summary>
              <div className="older-cycles-list">
                {cycles.slice(1).map((cycleId) => {
                  const cycle = state.council.cycles[cycleId];
                  return cycle ? <CycleCard key={cycleId} cycle={cycle} /> : null;
                })}
              </div>
            </details>
          )}
        </>
      )}
    </section>
  );
}

function CycleCard({
  cycle,
}: {
  cycle: NonNullable<ReturnType<typeof useStream>["state"]["council"]["cycles"][string]>;
}) {
  return (
    <article className="cycle-card panel" aria-label={`周期 ${cycle.cycleId}`}>
      <header className="cycle-head">
        <h3 className="digit-heading">
          <DigitSectionMark role="fusion" seed={cycle.cycleId} />
          <span>{cycle.cycleId}</span>
        </h3>
        <code title={cycle.evidenceHash}>{shortHash(cycle.evidenceHash)}</code>
        <span className={`state-badge state-${cycle.result?.status ?? "none"}`}>
          {cycle.result?.status ?? "running"}
        </span>
      </header>

      {cycle.claims.length > 0 && (
        <section className="cycle-section" aria-label="主张">
          <h4 className="digit-heading">
            <DigitSectionMark role="architecture" seed={`${cycle.cycleId}-proposed`} />
            <span>Proposed</span>
          </h4>
          <ul className="claim-list">
            {cycle.claims.map((claim) => (
              <ClaimRow key={claim.claim_id} claim={claim} />
            ))}
          </ul>
        </section>
      )}

      {cycle.challenges.length > 0 && (
        <section className="cycle-section" aria-label="挑战">
          <h4 className="digit-heading">
            <DigitSectionMark role="skeptic" seed={`${cycle.cycleId}-challenged`} />
            <span>Challenged</span>
          </h4>
          <ul className="challenge-list">
            {cycle.challenges.map((challenge) => (
              <ChallengeRow key={challenge.challenge_id} challenge={challenge} />
            ))}
          </ul>
        </section>
      )}

      {cycle.rejections.length > 0 && (
        <section className="cycle-section" aria-label="策略拒绝">
          <h4 className="digit-heading">
            <DigitSectionMark role="feng_shui" seed={`${cycle.cycleId}-policy`} />
            <span>Policy rejections</span>
          </h4>
          <ul className="rejection-list">
            {cycle.rejections.map((rejection) => (
              <RejectionRow key={rejection.rejection_id} rejection={rejection} />
            ))}
          </ul>
        </section>
      )}

      {cycle.result && (
        <section className="cycle-section" aria-label="最终结论">
          <h4 className="digit-heading">
            <DigitSectionMark role="fusion" seed={`${cycle.cycleId}-final`} />
            <span>Final</span>
          </h4>
          <div className="final-card">
            <p className="final-headline">{cycle.result.headline}</p>
            <p className="final-summary">{cycle.result.summary}</p>
            <dl className="scores">
              <div>
                <dt>测量质量 cap</dt>
                <dd>{cycle.result.sensor_confidence_cap.toFixed(3)}</dd>
              </div>
              <div>
                <dt>模型支持</dt>
                <dd>{cycle.result.model_support.toFixed(3)}</dd>
              </div>
              <div>
                <dt>display_confidence</dt>
                <dd>{cycle.result.display_confidence.toFixed(3)}</dd>
              </div>
              <div>
                <dt>推理一致性</dt>
                <dd>
                  {cycle.result.interpretation_agreement.supporting} 一致 /{" "}
                  {cycle.result.interpretation_agreement.contradicting} 分歧 /{" "}
                  {cycle.result.interpretation_agreement.unresolved_challenges} 未解决
                </dd>
              </div>
            </dl>
            <ul className="limitation-list">
              {cycle.result.limitations?.map((item, index) => (
                <li key={`${index}-${item}`}>{item}</li>
              ))}
            </ul>
          </div>
        </section>
      )}
    </article>
  );
}

function ClaimRow({ claim }: { claim: AgentClaim }) {
  const persona = personaFor(claim.role);
  return (
    <li className="claim-row">
      <AgentDigitField
        role={claim.role}
        seed={claim.claim_id}
        label={`${persona.name} Agent 的数字角色视觉隐喻；不表示现场物体识别`}
      />
      <div className="claim-main">
        <span className={`role-dot role-${claim.role}`} aria-hidden="true" />
        <span className="claim-persona" title={persona.tagline}>
          <PersonaMark role={claim.role} />
          {persona.name}
        </span>
        <span className="claim-role">{claim.role}</span>
        {claim.lens && (
          <span className={`lens-badge lens-${claim.lens}`}>
            {claim.lens === "metaphor" ? "隐喻解读" : "传感器解读"}
          </span>
        )}
        <span className={`state-badge state-${claim.state}`}>{claim.state}</span>
        <span className="claim-stance">{claim.stance}</span>
      </div>
      <p className="claim-proposition">{claim.proposition}</p>
      {claim.systematic_reading && (
        <SystematicReadingBlock reading={claim.systematic_reading} />
      )}
      <details className="claim-details">
        <summary>来源 · 数据分析路径 · 分析过程 · 参考文章</summary>
        <div className="claim-detail-block">
          <h5 className="digit-heading digit-heading-compact">
            <DigitSectionMark role="architecture" seed={`${claim.role}-${claim.proposition}-sources`} />
            <span>来源与参考文章</span>
          </h5>
          <ul className="claim-sources">
            {(claim.sources?.length ? claim.sources : ["—"]).map(
              (source, index) => (
                <li key={`${index}-${source}`}>
                  {source.startsWith("http") ? (
                    <a href={source} target="_blank" rel="noopener noreferrer">
                      {source.replace(/^https?:\/\//, "").slice(0, 80)}
                    </a>
                  ) : (
                    source
                  )}
                </li>
              ),
            )}
          </ul>
        </div>
        <div className="claim-detail-block">
          <h5 className="digit-heading digit-heading-compact">
            <DigitSectionMark role="soundscape" seed={`${claim.role}-${claim.proposition}-path`} />
            <span>数据分析路径</span>
          </h5>
          <div className="evidence-chips" aria-label="证据引用">
            {claim.evidence_refs.map((ref) => (
              <code key={ref} className="evidence-chip" title={ref}>
                {shortHash(ref, 18)}
              </code>
            ))}
          </div>
        </div>
        <div className="claim-detail-block">
          <h5 className="digit-heading digit-heading-compact">
            <DigitSectionMark role="psyche" seed={`${claim.role}-${claim.proposition}-process`} />
            <span>分析过程</span>
          </h5>
          <p className="claim-process">
            {claim.process || "读取证据标量并映射为隐喻意象。"}
          </p>
          {claim.analysis_steps?.length ? (
            <ol className="analysis-trace" aria-label="分析轨迹">
              {claim.analysis_steps.map((step, index) => (
                <li key={`${step.step_id}-${index}`} className={`trace-step trace-${step.phase}`}>
                  <div className="trace-head">
                    <span className={`trace-phase trace-phase-${step.phase}`}>
                      {step.phase}
                    </span>
                    <span className="trace-title">{step.title}</span>
                    <span className="trace-index">{index + 1}</span>
                  </div>
                  <p className="trace-text">{step.text}</p>
                  {step.evidence_refs?.length ? (
                    <div className="evidence-chips" aria-label="本步骤证据">
                      {step.evidence_refs.map((ref) => (
                        <code key={ref} className="evidence-chip" title={ref}>
                          {shortHash(ref, 18)}
                        </code>
                      ))}
                    </div>
                  ) : null}
                </li>
              ))}
            </ol>
          ) : (
            <p className="claim-process">
              本周期未记录逐步推理轨迹;仅保留证据映射摘要。
            </p>
          )}
        </div>
      </details>
      <details className="claim-more">
        <summary>验证边界与替代解释</summary>
        {claim.alternative_explanations?.length ? (
          <ul className="claim-alternatives">
            {(claim.alternative_explanations ?? []).map((item, index) => (
              <li key={`${index}-${item}`}>替代: {item}</li>
            ))}
          </ul>
        ) : null}
        <p className="claim-falsify">证伪: {claim.falsification_test}</p>
        <p className="claim-reasoning">{claim.reasoning_summary}</p>
      </details>
    </li>
  );
}

function SystematicReadingBlock({
  reading,
}: {
  reading: NonNullable<AgentClaim["systematic_reading"]>;
}) {
  return (
    <section className="systematic-reading" aria-label="系统解读">
      <h4 className="digit-heading">
        <DigitSectionMark role="feng_shui" seed="systematic-reading" />
        <span>系统解读</span>
      </h4>
      <p className="reading-scene">{reading.scene_sketch}</p>
      <ol className="reading-layers">
        {reading.layers.map((layer) => (
          <li key={layer.signal} className={`reading-layer reading-${layer.signal}`}>
            <div className="reading-layer-head">
              <span className="reading-signal">{layer.signal}</span>
              <code className="reading-state">{layer.state}</code>
              <span className="reading-metaphor">{layer.metaphor}</span>
            </div>
            <p className="reading-explanation">{layer.explanation}</p>
          </li>
        ))}
      </ol>
      {(reading.narrative || reading.boundary_notes?.length || reading.multimodal_hints?.length) ? (
        <details className="reading-more">
          <summary>完整叙事、边界与延伸提示</summary>
          <p className="reading-narrative">{reading.narrative}</p>
          {reading.boundary_notes?.length ? (
            <ul className="reading-boundaries">
              {reading.boundary_notes.map((note) => (
                <li key={note}>{note}</li>
              ))}
            </ul>
          ) : null}
          <div className="reading-hints">
            <ul>
              {reading.multimodal_hints?.map((hint) => (
                <li key={hint}>{hint}</li>
              ))}
            </ul>
          </div>
        </details>
      ) : null}
    </section>
  );
}

function ChallengeRow({ challenge }: { challenge: AgentChallenge }) {
  return (
    <li className="challenge-row">
      <div className="claim-main">
        <span className="challenge-category">{challenge.category}</span>
        <span className={`state-badge severity-${challenge.proposed_severity}`}>
          {challenge.proposed_severity}
        </span>
        <span className={`state-badge state-${challenge.status}`}>{challenge.status}</span>
      </div>
      <p>{challenge.statement}</p>
      <p className="claim-falsify">解除测试: {challenge.resolution_test}</p>
      {challenge.evidence_refs?.length ? (
        <div className="evidence-chips">
          {challenge.evidence_refs.map((ref) => (
            <code key={ref} className="evidence-chip" title={ref}>
              {shortHash(ref, 18)}
            </code>
          ))}
        </div>
      ) : null}
    </li>
  );
}

function RejectionRow({ rejection }: { rejection: PolicyRejection }) {
  return (
    <li className="rejection-row">
      <code className="rejection-code">{rejection.reason_code}</code>
      <span>{rejection.detail}</span>
    </li>
  );
}
