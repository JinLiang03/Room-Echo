# Repository Instructions

## Outcome

Build a reproducible ESP32 Wi-Fi CSI sensing demo with three calibrated proxy signals, an auditable multi-agent council, and a fluid web experience. Live hardware, recorded replay, and deterministic mock sources must share the same contracts.

## Non-negotiable truthfulness

- Never describe the output as camera-equivalent imaging, perfect through-wall vision, identity recognition, pose recovery, person counting, or metric depth.
- Keep raw sensor confidence separate from agent agreement.
- `final_claim_confidence <= sensor_confidence_cap` must hold in code and tests.
- If prerequisites or evidence are insufficient, output an explicit unknown state.
- Label every generative visualization as an inference field, not a camera image.

## Work discipline

- Read `PROJECT_INDEX.yaml`, `STATE.md`, `TASKS.md`, and the active phase prompt before changing code.
- Work only on the active phase. Do not silently implement later phases.
- Before coding, inspect existing files and preserve working behavior.
- Update `STATE.md` and `TASKS.md` only after validation proves a gate passed.
- Never weaken, delete, skip, or mark a test xfail merely to pass a phase.
- Do not add a new production dependency without documenting why the standard library or an existing dependency is insufficient.

## Architecture rules

- Firmware callbacks must enqueue compact records and return quickly; parsing, logging, or blocking I/O must not run in the Wi-Fi CSI callback.
- Raw capture is append-only. Derived data is reproducible from raw data plus a versioned calibration profile.
- The UI stream must never wait for an LLM call.
- Agent inference consumes compact `FeatureWindow` / `SignalTriplet` objects, never raw CSI arrays.
- API credentials remain server-side and are never included in firmware, browser bundles, logs, fixtures, or screenshots.
- Every cross-service message has `schema_version`, `session_id`, timestamp, source mode, and quality fields.

## Preferred stack

- Python 3.11+, FastAPI, Pydantic v2, NumPy, SciPy, Polars/PyArrow.
- React + TypeScript + Vite; strict TypeScript.
- OpenAI Agents SDK behind an `AgentProvider` interface with a deterministic mock.
- pytest, Hypothesis, Vitest, Playwright.

## Required checks

Run the narrowest relevant checks during development, then the full phase gate:

```bash
python -m ruff check .
python -m mypy services packages
python -m pytest -m "not hardware"
npm --prefix apps/web run lint
npm --prefix apps/web run typecheck
npm --prefix apps/web run test
npm --prefix apps/web run build
```

When browser behavior changes, run Playwright and inspect screenshots at 1440×900 and 390×844. When firmware changes, run `idf.py build` for both TX and RX. Hardware tests are never required for replay-only phases but must not be claimed as passed.

## Definition of done

A phase is done only when its deliverables exist, all applicable checks pass, evidence is recorded in `STATE.md`, and no known blocker is hidden. The full project is done only when Replay E2E passes, Live hardware gates are either passed or explicitly listed as pending, and the final claims match the measured evidence.

