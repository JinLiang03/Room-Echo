# ADR 0002 — Collector inputs: wire codec, recording, and replay

- Status: accepted
- Date: 2026-08-06

## Context

Phase 03 must make live serial, recorded replay, and deterministic mock
sources interchangeable behind one `FrameSource` interface, record raw frames
append-only, and verify replay bundles. The wire protocol implemented in
Phase 02 (`firmware/shared/python`) must stay the single codec so parser
behavior cannot drift between firmware, collector, and tests.

## Decision

1. The wire codec lives in the importable package `wsc_wire`
   (`firmware/shared/python/wsc_wire`), installed into the Python environment
   from the monorepo root; the collector imports it directly.
2. `NormalizedCsiFrame` ↔ wire conversion is lossless for fields the wire
   carries (seq, device_ts_us, rx_id, tx_id_hash, channel, bandwidth, rssi,
   noise, csi_iq). Fields the wire does not carry (session_id, source_mode,
   host_ts_ns, quality) are derived deterministically: replay derives
   `host_ts_ns = device_ts_us * 1000` so the same bundle replays byte-identical
   frames. `source_mode` is relabeled (`replay`) by contract.
3. Recording is append-only to a temp bundle (zstd-compressed raw wire
   frames + NDJSON events); `finalize()` fsyncs, writes manifest and
   `checksums.sha256`, then atomically renames the directory. `abort()`
   publishes the bundle as `incomplete` with an `INCOMPLETE` marker. Never
   overwrite an existing bundle.
4. Replay verification rejects missing files, checksum mismatches, manifest
   schema violations, path traversal/absolute paths, symlinks escaping the
   bundle root, and oversized decompressed raw data (zip-bomb style).
5. Live serial requires explicit ports (`--rx-a`, `--rx-b`); the source never
   guesses devices. Reconnects start a new epoch and reset the parser so stale
   partial frames cannot be mispaired.
6. Pairing is derived, not stored: raw stays append-only, pairing counters
   surface as events/health.

## Dependencies added

- `zstandard` — zstd is the mandated replay container (`raw.csi.zst`);
  Python's stdlib has no zstd codec.
- `pyserial` — USB/UART access for the two RX links; stdlib has no serial
  port support.

## Consequences

- A wire-protocol change must be made in `wsc_wire` and the firmware C in
  lockstep (golden test enforces this).
- Replay output is deterministic for the same bundle; live path stamps real
  host receive time in derived layers, never in raw.
- Security failures reject the whole bundle; no partial interpretation.
