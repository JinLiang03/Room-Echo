# Calibration protocol

Calibration creates a versioned `CalibrationProfile` that maps raw
`FeatureWindow` statistics to the three proxy signals. The mock workflow is
fully validated; the live protocol is gated on Phase 11 hardware.

## Mock (always available)

```bash
make calibration-wizard          # mock scenario demo_room_v1 -> data/calibration
make evaluate-calibration        # held-out metrics + checksum verification
```

## Protocol (live, when unblocked)

1. 30 s warmup, 120 s empty-room baseline.
2. 3× standard walk trials.
3. Occupancy levels (low/medium/high) with static obstruction.
4. 5-point depth axis trials.
5. Held-out trials kept separate from train/validation.

Discipline (from `prompts/11_HARDWARE_VALIDATION.md`):

- Parameters are tuned on train/validation trials only; test trials are never
  re-inspected to adjust thresholds.
- Any hardware/position/channel change creates a **new** profile and test run.
- Failed trials are never deleted; a protocol violation may exclude them only
  with the reason and raw data preserved.
- Acceptance thresholds are never lowered; a failing signal is renamed,
  downgraded, or set to `unknown`.
- Results are valid only for the recorded room/topology/firmware/profile.

See `docs/HARDWARE_AND_CALIBRATION.md` for the canonical spec and
`data/calibration/demo_room_v1/profile.json` for the current (simulated)
profile.
