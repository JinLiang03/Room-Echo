# WiFi Spatial Council — Operator Guide

## What this is

A local ESP32 Wi-Fi CSI demo that produces **three calibrated proxy signals**
(motion intensity, occupancy/obstruction density proxy, depth zone proxy),
an **auditable multi-agent council** that explains and challenges them, and a
**web experience** with an abstract "radio interference field" and an
optional soundscape. Everything is a proxy — never camera imaging, identity,
person counts, pose, or metric distance.

## First install

Requirements: Python 3.11–3.13, Node.js 20+ (24 used), Google Chrome for E2E.

```bash
make setup            # uv sync, contracts/schemas/types/fixtures, npm install
make verify-contracts # contract drift check
make test             # full non-hardware test suite
```

Firmware build (optional; needs ESP-IDF 5.5+):

```bash
make firmware-build
```

## Replay demo (no hardware needed)

```bash
make demo MODE=replay SCENARIO=walk_through     # 10 s short demo
make demo MODE=replay SCENARIO=demo_2min        # scripted 2-minute demo
make demo MODE=mock SCENARIO=interference       # live-generated mock
```

This starts the API on :8000 and the web app on :5173 with the demo session
auto-started. Open http://127.0.0.1:5173/#/home.

Manual alternative:

```bash
uv run python scripts/run_demo.py --mode replay --scenario demo_2min
```

The demo fixture (idle → far entry → approach → occupancy change → ambiguous
interference → recovery) is frozen at `data/fixtures/demo_2min`; the mock
council produces claims, a material challenge, a revision/concession, a
policy rejection, and a fused result during the run.

## Live preparation (Phase 11 hardware)

```bash
make live \
  RX_PORTS=rx-a=/dev/ttyUSB0,rx-b=/dev/ttyUSB1 \
  LIVE_TOPOLOGY_HASH=sha256:REPLACE_WITH_64_HEX \
  CALIBRATION_PROFILE=data/calibration/live_room_v1/profile.json
```

Ports are explicit — the system never guesses devices. Live status in the
release report stays `blocked_by_hardware` until boards/antennas/room
geometry are recorded and validated in Phase 11.

The current automated hardware tooling performs serial capture sanity only.
Live calibration, held-out acceptance, and live-vs-replay comparison targets
remain explicit non-zero gates until the raw recording pipeline is connected;
see `docs/LIVE_SETUP.md` before handing results back.

## Common faults (injectable during a session)

`POST /api/stream/faults/{name}` with `{"active": true, "params": {...}}`:

| fault | effect |
| --- | --- |
| `packet_loss` (`ratio`) | drops frames → degraded/unknown within two windows |
| `single_rx` | keeps only one link → depth unknown, motion continues |
| `tx_stale` | pauses the source → stale overlay, state cleared |
| `profile_mismatch` | occupancy/depth unavailable (uncalibrated) |
| `llm_timeout` | council hits the 15 s deadline → audited degraded baseline |
| `invalid_json` | bad provider output → Policy rejection in the audit |
| `disk_error` | simulated storage alert |

`make fault-injection` runs the pytest suite for all of these.

## Data locations

| path | content |
| --- | --- |
| `data/fixtures/` | frozen replay bundles (`walk_through`, `demo_2min`) + contract fixtures |
| `data/calibration/demo_room_v1/` | simulated calibration profile |
| `data/derived/evidence/` | sealed EvidencePacket audit (NDJSON) |
| `data/derived/council/` | council cycle audit (NDJSON) |
| `data/derived/stream/` | full WebSocket event logs per session (NDJSON) |
| `data/derived/features/` | extracted FeatureWindows (parquet) |
| `artifacts/` | QA reports, screenshots, perf/soak/release reports |

## Privacy

- Raw CSI never leaves the server; agents receive only sealed compact
  EvidencePackets.
- No ground truth enters packets, prompts, or traces (hidden by default in
  the UI).
- Logs record model/latency/status/usage, never API keys or raw MACs.
- Every page shows `INFERENCE FIELD — NOT A CAMERA IMAGE`.

## Release verification

```bash
make soak-replay DURATION=60m
uv run python scripts/verify_release.py --mode replay --output artifacts/release_report.json
```

The report marks every non-hardware gate `passed | failed | not_run`; live
gates are `blocked_by_hardware` until real evidence exists.
