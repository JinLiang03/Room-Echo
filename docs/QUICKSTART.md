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
