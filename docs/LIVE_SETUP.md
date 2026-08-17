# Live setup (Phase 11 — currently blocked)

Live validation is `blocked_by_hardware` until the following is true on the
target machine (see `hardware/hardware_inventory.json`):

1. Three ESP32-S3 boards connected over USB with **explicit, confirmed**
   serial ports for TX / RX-A / RX-B.
2. Antennas attached, boards powered, and a non-collinear triangular topology
   fixed with recorded board positions and antenna directions.
3. Room geometry recorded (walls/furniture), channel scan completed, and a
   5-point depth axis laid out for calibration.

When ready:

```bash
make hardware-sanity RX_PORTS=rx-a=/dev/cu.X,rx-b=/dev/cu.Y TX_PORT=/dev/cu.Z
make live \
  RX_PORTS=rx-a=/dev/cu.X,rx-b=/dev/cu.Y \
  LIVE_TOPOLOGY_HASH=sha256:REPLACE_WITH_64_HEX_FROM_TOPOLOGY_JSON \
  CALIBRATION_PROFILE=data/calibration/live_room_v1/profile.json
```

`hardware-sanity` refuses to run unless the three ports exist and the operator
has confirmed the physical mapping (the tooling never guesses ports or flashes
unknown devices). `make live` explicitly exports `APP_MODE=live`, autostarts the
session, and passes both RX ports to the API. It also refuses to start without
an explicit topology hash and an integrity-valid, active, matching,
non-simulated recorded profile; Mock/demo calibration is never accepted by
Live mode.

The following acceptance stages are specified but are **not implemented as
automated commands in this checkout**: live calibration, held-out hardware
acceptance, and live-vs-replay equivalence. Their Make targets deliberately
return non-zero. Do not record them as passed until they consume an append-only
raw bundle, a non-simulated matching calibration profile, and the required
held-out evidence from `docs/ACCEPTANCE_TESTS.md`.

Firmware binaries are ready but **not flashed**; exact build hashes are in
`firmware/build/manifest.json` and `hardware/`.
