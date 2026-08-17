# ADR 0008 — Agent-selected generative visual themes

- Status: accepted
- Date: 2026-08-10

## Context

The Home field previously used only `abstract_presence`, while the seven-role
Council could only add colour and response overlays. That made the Agent's
spatial-life reading difficult to perceive. The product now needs a stronger
relationship between Fusion's bounded interaction and the visual body without
turning generated furniture or a floor plan into a sensing claim.

## Decision

1. Fusion may select only from the deterministic `SpatialThemeId` allowlist.
   Effects such as `expand`, `startle`, and `contract` map to presentation
   metaphors such as a seat, lamp, and floor plan.
2. Home introduces each active session through `floorplan → volume → selected
   theme`, then morphs between later Fusion selections through the digit river.
3. Signal-driven motion, density, relative layering, clarity, and confidence
   remain independent of theme selection. Home passes no Council result into
   the scalar render mapper; the Agent result selects the target template only.
4. Every theme remains explicitly a generated inference-field visual and never
   means that CSI detected a real object, room layout, person, or furniture.

## Consequences

- Agent presence becomes legible in the central visual body, not only in text
  or a response overlay.
- The runtime stays deterministic and testable: the same approved Fusion effect
  maps to the same theme, while the sealed signal snapshot still controls the
  numeric animation parameters.
- A semantic result can change presentation even when its `cycle_status` is
  ambiguous; the UI must retain the honest semantic status and boundary copy.
