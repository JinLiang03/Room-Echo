# Quickstart

Run the full replay demo in under a minute (no hardware needed).

```bash
make setup          # uv sync + contracts/schemas/types/fixtures + npm install
make verify-contracts
make demo MODE=replay SCENARIO=demo_2min
```

Open http://127.0.0.1:5173/#/home

The API listens on :8000 (health: `/healthz`), the web app on :5173, and the
demo session auto-starts. `make demo` repeats the selected Replay/Mock source,
creating a new session id on every pass so the simulated field stays active
during presentation. The loop is never enabled for Live mode. Other quick
checks:

```bash
make test           # full non-hardware suite
make e2e-replay     # service-layer + full-stack Playwright E2E
make fault-injection
make multimodal-perf-smoke
```

See [README-OPERATOR.md](../README-OPERATOR.md) for the operator guide and
`docs/DEMO_SCRIPT.md` for the two-minute demo narrative.

For the production-equivalent, same-origin competition build:

```bash
make submission-demo PORT=8000
```

Open http://127.0.0.1:8000/#/home. This enables `PUBLIC_REPLAY=1`: the server
is pinned to the simulated `demo_2min` Replay, autostarts/loops it, serves the
Vite build, and rejects anonymous stream/fault/WebSocket control. It uses the
deterministic Mock Provider by design, so this command does **not** prove a
real model call. Inspect the evaluator-friendly result with:

```bash
curl --fail http://127.0.0.1:8000/api/agent/latest
curl --fail -H 'content-type: application/json' \
  -d '{"focus":"overview","wait_timeout_s":5,"require_openai":false}' \
  http://127.0.0.1:8000/api/agent/query
```

The MCP endpoint is Streamable HTTP at `http://127.0.0.1:8000/mcp/` and
exposes only `get_system_health` and `invoke_room_echo`. The second tool is a
bounded external-provider call, not a read-only status query. Verify the
official client handshake and tool calls with:

```bash
uv run python -m pytest tests/api/test_mcp_api.py -q
```

The old single-role smoke remains useful during provider development, but the
competition proof must use the full synchronous Council endpoint and keeps the
key server-side:

```bash
COUNCIL_OPENAI_SMOKE=1 OPENAI_API_KEY=... \
  uv run python -m pytest tests/council/test_providers.py -m openai_smoke -q

COUNCIL_DEEPSEEK_SMOKE=1 DEEPSEEK_API_KEY=... \
  uv run python -m pytest tests/council/test_providers.py -m deepseek_smoke -q
```

For the Render profile use `make verify-deepseek-council URL=https://...`; it
checks phase coverage, provider provenance, token/latency records, and the
sensor-confidence cap before writing a sanitized evidence report. The looping
presentation remains Mock-backed; only this bounded endpoint spends model
tokens. `make verify-openai-council URL=https://...` remains available for an
OpenAI-configured deployment.

See `docs/DEPLOY_PUBLIC_REPLAY.md` for Docker/Render deployment and the
one-worker runtime boundary. Live remains blocked until the explicit hardware
and calibration gates in `docs/LIVE_SETUP.md` pass.
