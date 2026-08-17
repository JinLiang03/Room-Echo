# Contributing

## Ground rules

- Read `PROJECT_INDEX.yaml`, `STATE.md`, `TASKS.md`, and the active phase
  prompt before changing code.
- Work only on the active phase; never silently implement later phases.
- Never weaken, delete, or xfail a test to pass a phase.
- Every cross-service message carries schema_version/session/timestamp/
  source mode/quality; Pydantic contracts are the single source of truth
  (regenerate with `make schemas` / `make fixtures`).
- Never describe outputs as camera/through-wall/identity/pose/people/metric
  depth; keep `final_claim_confidence <= sensor_confidence_cap`.
- No new production dependency without documenting why the stdlib or an
  existing dependency is insufficient.

## Checks before committing

```bash
uv run python -m ruff check .
uv run python -m mypy services packages
uv run python -m pytest -m "not hardware"
npm --prefix apps/web run lint
npm --prefix apps/web run typecheck
npm --prefix apps/web run test
npm --prefix apps/web run build
make verify-contracts
```

For browser changes run `npm --prefix apps/web run test:e2e`; for firmware
changes run `make firmware-build`. Update `STATE.md`/`TASKS.md` only after a
gate passes, and record evidence rather than claims.

## Frontend / hardware parallel workflow

Use one shared remote and one ancestry. Do not initialize the colleague's
copied folder as an unrelated repository.

Keep that remote private for now: this repository does not yet contain a
project-level `LICENSE`. Choose and review the intended license before making
the repository public; third-party dependency licenses do not license this
project's own source code.

- `main` is the last validated baseline; tag every demo baseline before work
  splits.
- Frontend-only work starts from `feat/frontend-v2` and normally stays inside
  `apps/web/`.
- Firmware, port/topology metadata, and on-site validation work starts from
  `hardware/live-validation`.
- Cross-service changes land contract-first in `packages/contracts/`, followed
  by regenerated schemas, TypeScript types, and a deterministic Replay fixture.
- Raw CSI and calibration runs are checksummed artifacts, not ordinary source
  commits. Never use `git add .` on a hardware machine; inspect staged paths and
  sizes first.

Each hardware handback must identify the source commit, firmware hashes,
contracts version, explicit board roles/ports, topology hash, non-simulated
calibration profile checksum, raw bundle checksum, and generated acceptance
reports. A final demo tag is valid only when its manifest pins all of those
identifiers plus the frontend/backend commit and the Replay E2E evidence.
