# Troubleshooting

## Web shows “连接已断开” / stale overlay

The API is not reachable. Start it with `make dev MODE=replay` or
`uv run uvicorn wifi_api.app:app --port 8000`. The app intentionally stops
pretending data is live when disconnected.

## Council shows “讨论不可用”

No evidence has been sealed yet, or the provider is offline. With the mock
provider this resolves within a few seconds of the demo starting; with the
OpenAI provider, set a server-side key or accept the mock fallback.

## Ports / live mode

Live mode requires explicit `RX_PORTS=rx-a=…,rx-b=…`; the system never guesses
devices. Missing or unconfirmed ports produce `blocked_by_hardware` (see
`docs/LIVE_SETUP.md`).

## Replay bundle rejected

`BundleVerifier` refuses corrupt/checksum-mismatched bundles by design.
Regenerate fixtures with `make generate-fixtures` and re-verify with
`make verify-replay REPLAY=data/fixtures/walk_through`.

## Perf below 60 FPS

The `#/perf` harness reports FPS/draws/dropped frames; `make
multimodal-perf-smoke` records an explicit fallback if a machine can't reach
60 FPS. Canvas 2D is the primary renderer by design (ADR 0006).

## Soak RSS growth above 10%

Recorded as a warning (monotonic high-water mark). Re-check with a memory
profiler; queue depth is bounded at 400 events and crashes are zero.
