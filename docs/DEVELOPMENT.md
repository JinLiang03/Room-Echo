# Local development

## Requirements

- `uv` (Python 3.11–3.13 is installed on demand into `.venv/`; the range is
  pinned below 3.14 because PyArrow wheels for CPython 3.14 on macOS arm64 are
  not yet available for the pinned line)
- Node.js 20+ and npm
- ESP-IDF is only needed from Phase 02 onward; it is not required for Phase 01.

## First-time setup

```bash
make setup
```

This installs the Python environment (`uv sync`), generates JSON Schemas, the
TypeScript contract types, the deterministic mock fixtures, and installs the
web dependencies.

## Running the dev stack

```bash
make dev MODE=replay
```

Starts:

- API on <http://127.0.0.1:8000> (`GET /healthz`)
- Web dev server on <http://127.0.0.1:5173> (proxies `/healthz`, `/api`, and
  `/ws` to the API)

The web page fetches `/healthz` and shows connection status, version, mode, and
component health. `MODE` must be one of `mock`, `replay`, or `live`.

## Checks

```bash
make lint          # ruff + web eslint
make typecheck     # mypy (services packages) + tsc
make test          # pytest (non-hardware) + vitest
make build         # production web build
make verify-contracts
```

`verify-contracts` regenerates schemas, TypeScript types, and fixtures into
temporary output, compares them against the checked-in files, and runs the
contract test suite. If it fails, run `make schemas fixtures` and commit the
generated output.

## Contract workflow

1. Edit the Pydantic models in `packages/contracts/wifi_contracts/`.
2. Run `make schemas` to refresh `schemas/*.schema.json`,
   `apps/web/src/generated/contracts.ts`, and
   `apps/web/src/generated/fixtures.ts`.
3. Run `make verify-contracts`; the drift check fails until generated files are
   committed.

Pydantic is the single source of truth. Never hand-edit the generated JSON
Schemas, TypeScript types, or fixtures.

## Environment

Copy `.env.example` to `.env` for local overrides. Never put a real
`OPENAI_API_KEY` in a committed file. Without a key, use `AGENT_PROVIDER=mock`.
