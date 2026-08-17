# ADR 0001 — Monorepo layout and generated contracts

- Status: accepted
- Date: 2026-08-06

## Context

The project must run the same contracts across three source modes (mock,
replay, live) and across Python (FastAPI/sensing/council), firmware, and a
React/TypeScript web client. Phase 01 needs a structure that later phases can
extend without drifting between three hand-written copies of the same shapes.

The repository previously contained only a prompt-engineering package (phase
0). It was not a git repository, and the system Python is 3.9, below the
required 3.11+, so toolchain setup must be reproducible.

## Decision

1. **Monorepo**: keep firmware, services, packages, web, data, and tests in one
   repository with one root `pyproject.toml` and one root `Makefile`.
2. **Pydantic is the structural source of truth.** Every cross-service message
   has a versioned Pydantic model in `packages/contracts/wifi_contracts/`.
3. **JSON Schema and TypeScript are generated**, not hand-written:
   - `scripts/generate_schemas.py` writes `schemas/*.schema.json`
   - `scripts/generate_types.py` writes `apps/web/src/generated/contracts.ts`
   - both ship with `--check` drift checks wired into `make verify-contracts`
4. **Deterministic fixtures**: `scripts/generate_fixtures.py` writes
   `data/fixtures/*.json` with a fixed seed and `source_mode=mock`; the check
   mode guarantees byte-stable reproducibility.
5. **uv** manages the Python environment (system Python 3.9 is too old).
   `requires-python` is pinned to `>=3.11,<3.14` because PyArrow ships no
   CPython 3.14 macOS arm64 wheels for the locked line; `uv.lock` records the
   dependency graph.
6. **No Docker dependency for the live path**: serial ports are host devices;
   the API runs directly on the host. Docker remains optional.

## Dependency rationale

The runtime stack is fixed by `PROJECT_INDEX.yaml` and `README.md`: FastAPI +
Pydantic v2 + NumPy + SciPy + Polars/PyArrow for the backend and OpenAI Agents
SDK for the council. These are locked in Phase 01 so later phases do not churn
the environment. `jsonschema` (schema validation) and `hypothesis` (invariant
property tests) are required by the acceptance gates. No database, message
queue, login system, or mobile app is added.

## Consequences

- A schema change is a code change; generated artifacts must be regenerated and
  committed together (`make verify-contracts` enforces this).
- Tests cover both model-level validation and the JSON Schema/TS views of the
  same fixtures, so drift is caught in CI.
- The web client never recomputes formal signals; it consumes generated types
  and derived payloads only.
- `final_claim_confidence <= sensor_confidence_cap` and probability-sum
  invariants live in Pydantic validators and are exercised by Hypothesis
  properties.
