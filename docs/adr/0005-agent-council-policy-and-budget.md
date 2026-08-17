# ADR 0005 — Agent council: structured debate, policy arbiter, call budget

- Status: accepted
- Date: 2026-08-06

## Context

Phase 07 must add a bounded, structured, auditable multi-agent debate that
increases alternative-explanation coverage and overreach detection without
letting agents manufacture sensor credibility. The acceptance contract is
`display_confidence <= model_support <= sensor_confidence_cap`, agreement must
never enter that formula, and the signal UI must never wait on an LLM call.

## Decision

1. **Providers return Structured Outputs only.** `AgentProvider` proposes
   `SpecialistProposal`, `ChallengeSet`, `ResponseOutput`, and
   `SynthesisOutput` Pydantic models via the OpenAI Agents SDK `output_type`;
   free-text JSON parsing is not a code path. The output schemas carry no
   numeric measurement fields, so a new measurement cannot structurally enter
   a claim; prose fabrication is additionally rejected by the policy language
   rules.
2. **Deterministic mock council.** `MockAgentProvider` uses a fixed seed and a
   versioned template (`mock-council.v1`); per-cycle choice is derived from a
   stable hash of the evidence packet, so repeated runs are byte-stable. It
   abstains on single-RX depth, raises a material confound for interference,
   and supports a controlled `misbehave` mode for policy rejection tests.
3. **Call budget counts attempts (retries included).** Default is 6 per
   cycle. Priority: propose (data quality + three specialists = 4) →
   red-team cross-examination (1) → one response per challenged claim while
   budget remains → Fusion provider call only if budget remains. When the
   budget is exhausted, response concessions and Fusion assembly are
   deterministic, so the UI always receives a result within the 15 s hard
   deadline and never waits on an unbounded LLM chain.
4. **Deterministic PolicyArbiter.** A program (never an LLM) validates in
   order: schema, cycle/evidence hash, evidence refs against the current
   sealed packet, forbidden language (person count, identity, pose, metric
   depth, health, wall presence, vision language), single-RX depth unknown,
   calibration/topology mismatch for occupancy/depth, confidence invariants,
   and challenge severity (category floor: confound/missing_evidence/
   contradiction → material; calibration_mismatch/causal_overreach/
   stale_evidence → blocking). Every rejection carries a stable reason code
   and is written to the audit log.
5. **Confidence is sensor-only.** `model_support = min(motion, occupancy,
   depth confidence)`; unresolved material/blocking challenges only lower the
   displayable state (ambiguous) and apply versioned penalty factors
   (`material_penalty=0.75`, `blocking_penalty=0.5`) — agreement and agent
   count never enter the formula. `unavailable`/`uncalibrated` force
   `display_confidence = 0` and prohibit presence narration.
6. **Scheduler keeps one active cycle + one latest pending slot.** New
   evidence replaces the pending slot; intermediate cycles are dropped by
   design (only the latest candidate matters, matching ARCHITECTURE.md).
   Commits are sequence-guarded so an older cycle can never overwrite a newer
   snapshot. The whole cycle runs under a 15 s deadline and falls back to an
   audited degraded baseline on timeout.
7. **Caching is scoped.** Provider outputs are cached by
   (provider, role, phase, prompt version + hash, model, evidence hash), so a
   cache never crosses schema, prompt, model, or evidence version.
8. **OpenAI provider is server-side and opt-in.** The API key is read only
   from the server environment; health probes report presence without the
   value, degraded health falls back to mock/baseline, and integration tests
   are opt-in (`COUNCIL_OPENAI_SMOKE=1`), never in default CI. Model names
   come from config/env and appear in provenance.

## Consequences

- The mock debate is a real testable council: specialists propose, RedTeam
  challenges, specialists respond or concede, the arbiter rejects, and Fusion
  copies approved numbers verbatim.
- Confidence is bounded by measured quality by construction and property
  tested; 1/3/6-agent runs, 100% agreement, and repeated evidence all yield
  the same display confidence.
- Every cycle produces an auditable `CouncilCycleDetail` (claims, challenges,
  rejections, calls, result) plus an append-only audit log.
