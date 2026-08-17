# Same-origin public Replay deployment

## What this deployment is

This profile publishes the validated **simulated Replay** experience on one
origin: FastAPI serves the Vite build, REST endpoints, and `/ws`. It is pinned
to `data/fixtures/demo_2min`, loops with a fresh session id, and uses one
Uvicorn worker because the active session and WebSocket recovery buffer are
process-local.

It is not a Live-hardware endpoint. No ESP32 was validated by this deployment,
and the three values remain calibrated proxy signals rather than a camera
image, identity, pose, people count, or metric depth.

## Local production-equivalent check

```bash
make submission-demo
```

Open `http://127.0.0.1:8000/#/home`, then verify:

```bash
curl --fail http://127.0.0.1:8000/healthz
curl --fail http://127.0.0.1:8000/api/stream/status
curl --fail http://127.0.0.1:8000/api/replay/bundles
curl --fail http://127.0.0.1:8000/api/agent/latest
curl -i -X POST http://127.0.0.1:8000/api/stream/stop
```

The four read-only requests should return `200`; the mutation must return `403`.
`SERVE_WEB=1` fails startup clearly when `apps/web/dist/index.html` is absent.
The local profile can validate Replay without a key. The final public MCP smoke
also calls the real provider and therefore runs only after the Render secret is
configured.

## Render Blueprint

1. Push this repository to a private GitHub repository.
2. In Render choose **New → Blueprint**, connect the repository, and select
   `render.yaml`.
3. When Render prompts for `DEEPSEEK_API_KEY`, enter it in Render's secret field;
   never paste it into Git, the browser app, screenshots, or submission files.
4. Deploy and wait for `/healthz` to pass.
5. Open the Render URL with `/#/home`, test WebSocket updates, reload once to
   verify snapshot recovery, and copy that HTTPS URL into the competition
   experience-link field.
6. Run `python scripts/mcp_smoke.py https://YOUR-SERVICE.onrender.com/mcp/ --provider deepseek`
   and provide that canonical URL if the evaluator accepts a direct MCP URL.
7. Record one sanitized full-Council proof:

   ```bash
   make verify-deepseek-council URL=https://YOUR-SERVICE.onrender.com
   ```

### Free-instance cold start

Render Free web services sleep after 15 minutes without inbound traffic and
need roughly a minute to wake. The Blueprint's `healthCheckPath` verifies a
running instance; it does not keep a Free instance awake. Before a timed
demonstration or evaluator handoff, pre-warm the service and then run the MCP
check while it is warm:

```bash
make warm-render URL=https://YOUR-SERVICE.onrender.com
make mcp-smoke \
  MCP_URL=https://YOUR-SERVICE.onrender.com/mcp/ \
  MCP_PROVIDER=deepseek
```

This warm-up never calls DeepSeek. It only waits for `/healthz` to return
`status=ok`.

There is no application-level switch that removes Render's sleep policy. For
the most predictable contest evaluation, upgrade this web service to a paid
instance, which stays running. Keep `plan: free` only when the cost-free
preview constraint matters, and pre-warm immediately before the timed test.

The Blueprint deliberately keeps the continuously looping presentation on
`AGENT_PROVIDER=mock`: coupling a two-minute loop to a paid provider would
create unbounded repeated calls. `POST /api/agent/invoke` and MCP
`invoke_room_echo` instead execute one complete DeepSeek-backed Council over the
latest integrity-verified EvidencePacket and cache the successful result for
the process lifetime. Repeated evaluation calls reuse that result. Failed
real-provider cycles are capped at two attempts per server process so an
anonymous retry loop cannot create unbounded model spend.

## Required public environment

| Variable | Value | Purpose |
| --- | --- | --- |
| `SERVE_WEB` | `1` | Serve `apps/web/dist` after API/WS routes |
| `PUBLIC_REPLAY` | `1` | Enable read-only, fail-closed public mode |
| `APP_MODE` | `replay` | Documentation and non-public fallback |
| `SCENARIO` | `demo_2min` | Documentation and non-public fallback |
| `DEMO_AUTOSTART` | `1` | Start without an anonymous control call |
| `DEMO_LOOP` | `1` | Continue the passive judging experience |
| `AGENT_PROVIDER` | `mock` | Deterministic, cost-bounded public loop |
| `PUBLIC_REAL_PROVIDER_INVOKE` | `1` | Enable one cached real Council invocation |
| `REAL_AGENT_PROVIDER` | `deepseek` | Select the one-shot evaluator provider |
| `DEEPSEEK_API_KEY` | Render secret | Server-side provider credential |
| `DEEPSEEK_BASE_URL` | `https://api.deepseek.com` | OpenAI-compatible API origin |
| `DEEPSEEK_COUNCIL_MODEL` | `deepseek-v4-flash` | Audited Council model |
| `REAL_COUNCIL_DEADLINE_S` | `120` | Bounded full-cycle deadline |

`PUBLIC_REPLAY=1` overrides conflicting mode/scenario/autostart/loop values to
`replay/demo_2min/autostart/loop`; this is deliberate fail-closed behavior.
`ProviderHealth.status=ok` means the secret is configured, not that a network
request succeeded. Only the verification command above proves the deployed
provider: it requires `provider=deepseek`, at least seven `status=ok` calls,
all three Council phases, token/latency provenance, and the confidence cap.

For Agent evaluation, `status=ready` means the requested API/provider
operation completed and returned an auditable reading. `cycle_status` remains
the semantic Council conclusion (`supported`, `ambiguous`, or `unavailable`),
so a technically ready call can honestly report `cycle_status=ambiguous`.

## Docker

```bash
docker build -t wifi-spatial-council-replay .
docker run --rm -p 8000:8000 wifi-spatial-council-replay
```

The image runs `uvicorn ... --workers 1` as an unprivileged user. Do not add a
second worker or expose the development Vite port; both break the single
session/same-origin delivery contract.

## Security boundary

In `PUBLIC_REPLAY=1`, anonymous callers cannot change the session, start Mock
or Live, pause/resume, step, seek, change rate, stop, record raw data, or inject
faults. WebSocket `hello` and `ping` stay enabled; a WebSocket control message
receives an explicit JSON error with status `403`. Only the sealed
`demo_2min` bundle is listed by the public replay API.
