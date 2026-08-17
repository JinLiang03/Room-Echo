# Competition Replay quick start

This submission runs the validated, simulated `demo_2min` Replay through the
same sensing, Evidence, Council, policy, WebSocket, and Web contracts used by
the project. It does **not** claim Live ESP32 hardware validation.

## One command

Prerequisites: Python 3.11–3.13, [uv](https://docs.astral.sh/uv/), and Node.js
22 (Node.js 18+ is supported by the Web project).

```bash
make submission-demo
```

Open <http://127.0.0.1:8000/#/home>. The target installs locked Python/Web
dependencies, builds the Web app, then serves UI, REST API, and WebSocket from
one FastAPI origin with one worker. Stop it with `Ctrl-C`.

Public Replay is supervisor-owned and read-only: it is pinned to
`replay/demo_2min`; anonymous start/stop/pause/seek/rate/step/record, fault
injection, Live/Mock starts, and WebSocket controls return `403`. Read-only
status, evidence, Council audit, and `hello`/`ping` remain available.

## Evaluator interfaces

The browser and automated evaluators share the same active Replay session:

- `GET /healthz` — service and pipeline health;
- `GET /api/agent/latest` — latest structured Agent reading;
- `POST /api/agent/query` — wait briefly for a reading, with explicit provider
  provenance and an optional fail-closed `require_provider` flag
  (`require_openai` remains backward compatible);
- `POST /api/agent/invoke` — single synchronous evaluator entry point; runs
  one real-provider Council cycle over sealed evidence, then caches it;
- `/mcp/` — MCP 2025-11-25 Streamable HTTP with two focused tools:
  `get_system_health` and `invoke_room_echo`.

The MCP surface deliberately does not mirror every backend route. Health is a
fast read-only call; `invoke_room_echo` is the one complete Agent task and is
annotated as an external provider call. Neither tool can access Live controls,
faults, recording, raw CSI, file paths, or credentials. With a server-side key
configured, verify the official MCP handshake and both tools with:

```bash
make mcp-smoke
```

The looping Replay Council remains deterministic to prevent unbounded spend.
Real model execution is isolated to the cached invocation endpoint and is
enabled only by `PUBLIC_REAL_PROVIDER_INVOKE=1` plus the selected server-side
credential. The current Render profile uses `REAL_AGENT_PROVIDER=deepseek` and
`DEEPSEEK_API_KEY`; DeepSeek contributes bounded narrative fields while the
server rebinds all measurements, evidence refs, reactions and multimodal
parameters to the sealed packet.

The evaluator-facing invocation separates execution from interpretation:
`status=ready` means the request and provider Council completed; the nested
`cycle_status` remains the honest semantic result and may be `ambiguous` when
the sealed WiFi evidence does not support a stronger conclusion. Render's
free preview may cold-start after inactivity; run `make warm-render
URL=https://YOUR-SERVICE.onrender.com` immediately before a timed evaluation.

The public preview at <https://wifi-spatial-council-replay.onrender.com> was
verified on commit `845f117` with `provider=deepseek`,
`model=deepseek-v4-flash`, and 10 real `status=ok` calls across propose,
cross-examine, respond and synthesize. Reproduce the fail-closed check with:

```bash
make verify-deepseek-council URL=https://wifi-spatial-council-replay.onrender.com
```

For a Docker/Render deployment and server-side model-key configuration, see
[`docs/DEPLOY_PUBLIC_REPLAY.md`](docs/DEPLOY_PUBLIC_REPLAY.md).
