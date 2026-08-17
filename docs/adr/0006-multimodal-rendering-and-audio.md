# ADR 0006 — Deterministic multimodal rendering and soundscape

- Status: accepted
- Date: 2026-08-07

## Context

Phase 09 must turn the three approved proxy signals and CouncilResult into a
rich but truthful multimodal experience: an abstract "radio interference
field" and a Web Audio soundscape. Replays must be byte-stable for the same
evidence, unknown/stale states must clear previous visuals, audio must never
autoplay, and the UI must not fabricate imaging content.

## Decision

1. **Canvas 2D is the primary renderer — no Three.js/WebGL dependency.**
   150 particles + 4 depth rings + 2 disagreement arcs render at 60 FPS in
   headless Chrome (measured 61 FPS, 156 draw calls, 0 dropped frames).
   Canvas 2D works everywhere the app runs, so there is no WebGL fallback
   gap; this avoids a large dependency and its bundle impact. If a future
   phase needs volumetric/WebGL effects, the renderer interface is the
   `SignalSculpture` component and can be swapped behind the same
   deterministic `RenderParams`.
2. **Everything visual is deterministic.** `mapRenderParams` implements the
   phase baseline exactly (`multimodal-v1`): particle_speed/pulse from
   motion, field_density from occupancy probabilities, z_layer_separation
   from depth ordinals, saturation/edge_diffusion from measurement quality,
   disagreement_phase from bounded interpretation disagreement only.
   Particles come from `mulberry32(VISUAL_SEED)` — never `Math.random()` —
   and animation advances only time. Same seed + input ⇒ same first frame
   and same render snapshot hash (tested).
3. **Unknown/stale clears residue.** Inactive states return to a dim,
   static, desaturated haze: activity eases to 0, layers collapse, and the
   previous animated state is not shown (pixel-sampled in E2E: unavailable
   is flat, dim, non-animated).
4. **Web Audio is gesture-gated and muted by default.** The
   `SoundscapeEngine` only creates its graph on `enable()` from a user
   gesture; master gain starts at 0. Mapping: motion→tempo,
   occupancy→lowpass cutoff + harmonic density, depth→stereo width +
   feedback delay, quality→clarity. Pause/stop/blur fade out; focus/return
   fades back in only when unmuted. No alarm-like or danger sounds; the
   disagreement beat is a very light phase beat only.
5. **Testability without a real audio backend.** The engine talks to a
   narrow `SoundGraph` interface; production uses the real Web Audio graph,
   tests use a fake graph. Node counts are bounded and stable under 2000+
   high-frequency updates (no WebGL/Audio node leak).
6. **Perf is measured, not assumed.** `#/perf?seconds=N&rate=Hz` drives a
   scripted event feed and publishes `window.__wscPerf`; the
   `multimodal-perf-smoke` Makefile target launches the harness headlessly,
   asserts FPS/dropped/event count/node stability, and writes
   `artifacts/web/perf-smoke.json`. A FPS below 60 is recorded as an
   explicit fallback rather than silently accepted.

## Consequences

- The sculpture is reproducible across replays and never resembles imaging,
  silhouettes, floor plans, thermal humans, or camera output (E2E asserts no
  `<img>` inside the sculpture and pixel-level dimness for unavailable).
- The watermarked result card shows headline, three signals, three quality
  dimensions, alternatives, limitations, evidence hash, and versions without
  mixing measurement, model, and agreement scores.
- Audio lifecycle (gesture, mute, blur, unmount) is unit-tested and the node
  budget is bounded; reduced motion renders a static frame instead of
  animating.
