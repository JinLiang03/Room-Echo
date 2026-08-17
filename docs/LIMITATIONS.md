# Limitations (read before believing anything)

This system measures **radio channel statistics**, not the world:

- No camera-equivalent imaging, through-wall vision, identity, person counts,
  pose, health, dangerous-behavior detection, or metric distance.
- `motion_intensity` is a calibrated 0–1 proxy for dynamic channel change.
- `occupancy_density_proxy` is a relative obstruction/occupancy proxy — not
  wall density, not people.
- `depth_zone_proxy` is a relative near/mid/far proxy on the calibrated axis —
  not meters, not 3D reconstruction.
- Outputs are valid only for the recorded room/topology/firmware/profile and
  are labeled `unknown` when evidence is insufficient (single RX, mismatch,
  packet loss, staleness, OOD).
- Confidence is bounded by measured quality
  (`display_confidence <= model_support <= sensor_confidence_cap`); agent
  agreement never raises it.
- All visualizations are abstract inferences with a permanent watermark.
- The backend ageing-in-place scenario is an explicitly synthetic workflow fixture:
  its anonymous resident, 58 m² six-zone home, 13-entry day, room labels, pet
  label, and fall-risk moment are not Wi-Fi detections. Room/pet context comes
  from simulated external labels, and the fall case is a manual drill.
- The public UI does not add a care selector, resident/layout/timeline cards, or
  extra provenance panels. Default Home loads one synthetic care day once and
  cycles its four moments every 8 seconds. Each frame atomically binds one
  hash-scoped Mock proxy triplet to the Agent, four actions, and inference
  field; `?care=...` only selects a deterministic initial frame. This is a
  workflow simulation, not live elder-care sensing.
- Care actions are simulated previews or withheld intents only. No light, speaker,
  family notification, or robot is connected; there is no executed/completed
  or acknowledged device state.
- Raw-data retention is currently operator-managed; automatic expiry/deletion
  is not implemented. Release and handoff packages exclude `data/raw` by
  default.

Current status: replay baseline validated; live hardware gates
`blocked_by_hardware` until Phase 11 is run with real boards.
