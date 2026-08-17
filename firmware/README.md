# firmware

Phase 02 fills this directory with ESP-IDF projects:

- `csi_tx/` — dedicated transmitter on a fixed channel/bandwidth.
- `csi_rx/` — CSI receiver(s) with a compact ring-buffer and binary serial output.
- `shared/` — shared packet framing and constants.

No firmware code exists yet; Phase 01 is the repository skeleton and contracts
only. Firmware callbacks must enqueue compact records and return quickly; no
parsing, logging, or blocking I/O inside the Wi-Fi CSI callback.
