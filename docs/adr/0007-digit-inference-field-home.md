# ADR 0007 — Digit inference-field home and user-selected themes

- Status: accepted
- Date: 2026-08-08

## Context

The release baseline already has an auditable dark `Observe` view and a deterministic `SignalSculpture`. The new art direction needs an immediate, light, character-built homepage with morphing furniture-like forms, while keeping replay/live/mock on one contract and avoiding any suggestion that CSI identified furniture or reconstructed a room.

## Decision

1. Add `Home` as a separate default route. It reads the existing `StreamState`; Observe/Council/Evidence/Replay, contracts, estimators and backend remain unchanged.
2. Keep `multimodal-v1` as the scalar mapping used by audio and the old sculpture. Add `digit-field-v1` as a presentation renderer layered on those same approved scalars.
3. Theme geometry is selected only by the user. CSI and Agent output cannot select `lounge/studio/passage/garden/atrium`; every selector and canvas alternative says the theme is not a detected object.
4. Canvas 2D remains the only runtime renderer. Equal-count deterministic point fields morph through one RAF; pointer movement writes only to a local ref. Unknown/stale resets signal-driven animation and shows a neutral static theme preview with explicit unknown copy.
5. Keep raw sensor confidence, model support/final confidence, and interpretation agreement visually separate. `final_claim_confidence <= sensor_confidence_cap` remains untouched.
6. Add exactly one production dependency: `lenis@1.3.26` (MIT) for long audit-page wheel interpolation. Native CSS smooth scrolling cannot provide the same wheel lifecycle or app-level reduced-motion control. Lenis never enters the stream/render data path.
7. Do not adopt Vanta/Three, React Bits ASCIIText, or GSAP in the first release. The first two add WebGL/pixel-readback cost; GSAP is not OSI-licensed and is unnecessary for one Canvas progress scalar.

## Consequences

- The first viewport can be artistic while the detailed views remain auditable.
- A viewer can always distinguish generated theme, measured proxies and Agent agreement.
- Design PNG/GIF are review artifacts only; runtime output is reproducible from state + theme + seed.
- The production dependency and license audit must be regenerated, and desktop/mobile browser screenshots plus the Replay E2E must pass before this post-release change is recorded complete.
