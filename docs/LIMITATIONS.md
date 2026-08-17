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
- Raw-data retention is currently operator-managed; automatic expiry/deletion
  is not implemented. Release and handoff packages exclude `data/raw` by
  default.

Current status: replay baseline validated; live hardware gates
`blocked_by_hardware` until Phase 11 is run with real boards.
