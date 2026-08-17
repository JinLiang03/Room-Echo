# ADR 0003 — MVP uses no cross-RX phase, AoA, or ToF

- Status: accepted
- Date: 2026-08-06

## Context

Multi-antenna and multi-receiver Wi-Fi sensing research often uses carrier
phase across RX chains for angle-of-arrival (AoA), time-of-flight (ToF), or
time-difference-of-arrival (TDoA). The project's three-board topology (one TX,
two RX) superficially looks multi-antenna, but the devices do not share a
clock, carrier phase, or synchronized sampling.

## Decision

The MVP signal pipeline:

- uses **amplitude and per-link shape statistics only**;
- treats **phase as single-RX-internal and unverifiable across devices**;
- never computes AoA, TDoA, absolute ToF, or cross-RX raw phase differences;
- reports `depth_zone_proxy` as a calibrated propagation-depth proxy with an
  explicit `unknown` state, never as metric distance.

## Rationale

1. ESP32 CSI provides no usable cross-device carrier-phase reference; the
   firmware and hardware docs do not guarantee synchronized clocks.
2. Any AoA/ToF claim would require a calibration domain this project has not
   validated; per the truth contract, unvalidated claims must not exist.
3. The acceptance tests (§2) explicitly forbid fabricating depth from
   unpaired phase.

## Consequences

- `PairedFeatures.amplitude_shape_asymmetry` is derived from amplitude
  shape correlation, not phase.
- Replay determinism is preserved because amplitude statistics depend only on
  the recorded IQ values.
- If a future phase adds cross-RX phase processing, it requires a new
  adapter, a new data domain, a new calibration protocol, and a new acceptance
  gate; it cannot reuse this phase's metrics.
