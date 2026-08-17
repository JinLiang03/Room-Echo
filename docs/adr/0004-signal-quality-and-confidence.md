# ADR 0004 — Signal quality and confidence gating

- Status: accepted
- Date: 2026-08-06

## Context

Phase 06 must turn FeatureWindows into three proxy signals with honest
uncertainty. Agent agreement must never influence sensor confidence, and the
system must say `unknown` instead of guessing when evidence is insufficient.

## Decision

1. **Conservative minimum**: each signal's quality is the minimum of the
   components it requires (packet coverage, paired coverage, carrier
   coverage, clock/order, calibration match, interference, OOD, staleness).
   No averaging hides a failing gate; the weakest required component decides.
2. **Confidence chain**: `signal_confidence <= signal_quality`;
   `sensor_confidence_cap = min(motion_q, occupancy_q, depth_q)`;
   `signal_confidence = min(raw_confidence, sensor_confidence_cap)`.
   `unknown`/`unavailable` states force `confidence = 0`.
3. **Motion is not density**: if the motion score reaches the configured
   freeze threshold, occupancy output is `unknown` (motion contamination),
   and quality drops; fast motion is never reinterpreted as obstruction.
4. **Single RX**: depth is always `unknown` without two links; occupancy is
   `unknown` when the fitted profile was trained on dual links; motion stays
   available with a `single_link` degraded flag.
5. **Agent isolation**: estimator inputs are FeatureWindow + profile only;
   there is no agent-count or agreement field anywhere in the estimator
   dependency graph or confidence formula.
6. **Staleness**: `estimate_stale()` emits unknown states with zero
   confidence and resets EMAs, so a gap never leaves stale residues.

## Consequences

- Confidence can never exceed measured quality by construction (property
  tests assert the chain).
- Degraded conditions surface as `degraded`/`insufficient_signal`/`unknown`
  rather than fabricated values.
- The same FeatureWindow + profile + version yields the same SignalTriplet
  and the same EvidencePacket hash (canonical JSON, sealed).
