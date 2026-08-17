PY := .venv/bin/python
UV := uv
WEB := apps/web
MODE ?= replay
SCENARIO ?= walk_through
AUTOSTART ?= 0
LOOP ?= 0
RX_PORTS ?=
LIVE_TOPOLOGY_HASH ?=
CALIBRATION_PROFILE ?=

.PHONY: setup dev live api web test lint typecheck build verify-contracts fixtures schemas types demo firmware-build firmware-host-tests test-collector generate-fixtures verify-replay replay-smoke test-sensing-core benchmark-sensing extract-features test-calibration calibration-wizard evaluate-calibration test-signals replay-signals test-council replay-council test-confidence-invariants multimodal-perf-smoke e2e-replay fault-injection soak-replay hardware-sanity calibrate-live test-hardware compare-live-replay release-check

setup:
	$(UV) sync
	$(UV) run python scripts/generate_schemas.py
	$(UV) run python scripts/generate_types.py
	$(UV) run python scripts/generate_fixtures.py
	npm --prefix $(WEB) install

dev:
	$(MAKE) -j2 api web

api:
	APP_MODE=$(MODE) SCENARIO=$(SCENARIO) DEMO_AUTOSTART=$(AUTOSTART) \
		DEMO_LOOP=$(LOOP) \
		RX_PORTS="$(RX_PORTS)" LIVE_TOPOLOGY_HASH="$(LIVE_TOPOLOGY_HASH)" \
		CALIBRATION_PROFILE="$(CALIBRATION_PROFILE)" \
		$(UV) run uvicorn wifi_api.app:app --host 127.0.0.1 --port 8000 --reload

web:
	npm --prefix $(WEB) run dev -- --host 127.0.0.1

test:
	$(UV) run python -m pytest -m "not hardware"
	npm --prefix $(WEB) run test

lint:
	$(UV) run python -m ruff check .
	npm --prefix $(WEB) run lint

typecheck:
	$(UV) run python -m mypy services packages
	npm --prefix $(WEB) run typecheck

build:
	npm --prefix $(WEB) run build

fixtures:
	$(UV) run python scripts/generate_fixtures.py

schemas:
	$(UV) run python scripts/generate_schemas.py
	$(UV) run python scripts/generate_types.py

verify-contracts:
	$(UV) run python scripts/generate_schemas.py --check
	$(UV) run python scripts/generate_types.py --check
	$(UV) run python scripts/generate_fixtures.py --check
	$(UV) run python -m pytest tests/contracts -q

demo:
	$(MAKE) dev MODE=$(MODE) SCENARIO=$(SCENARIO) AUTOSTART=1 LOOP=1

live:
	@test -n "$(RX_PORTS)" || (echo "RX_PORTS=rx-a=/dev/...,rx-b=/dev/... is required" >&2; exit 2)
	@test -n "$(LIVE_TOPOLOGY_HASH)" || (echo "LIVE_TOPOLOGY_HASH=sha256:... is required" >&2; exit 2)
	@test -n "$(CALIBRATION_PROFILE)" || (echo "CALIBRATION_PROFILE=data/calibration/.../profile.json is required" >&2; exit 2)
	$(MAKE) dev MODE=live AUTOSTART=1 LOOP=0 RX_PORTS="$(RX_PORTS)" \
		LIVE_TOPOLOGY_HASH="$(LIVE_TOPOLOGY_HASH)" \
		CALIBRATION_PROFILE="$(CALIBRATION_PROFILE)"

firmware-build:
	bash scripts/build_firmware.sh

firmware-host-tests:
	$(UV) run python -m pytest tests/firmware_contract -q

test-collector:
	$(UV) run python -m pytest tests/collector -q

generate-fixtures:
	$(UV) run python scripts/generate_fixtures.py

verify-replay:
	$(UV) run python -m wifi_collector.cli verify $(REPLAY)

replay-smoke:
	$(UV) run python -m wifi_collector.cli replay $(REPLAY) --no-pacing

test-sensing-core:
	$(UV) run python -m pytest tests/sensing -q

benchmark-sensing:
	$(UV) run python scripts/benchmark_sensing.py

extract-features:
	$(UV) run python scripts/extract_features.py --replay $(REPLAY) --recompute

test-calibration:
	$(UV) run python -m pytest tests/calibration -q

calibration-wizard:
	$(UV) run python scripts/calibration_wizard.py --mode mock --scenario demo_room_v1 --out data/calibration

evaluate-calibration:
	$(UV) run python scripts/evaluate_calibration.py --profile data/calibration/demo_room_v1

test-signals:
	$(UV) run python -m pytest tests/signals -q

replay-signals:
	$(UV) run python scripts/inspect_signals.py --replay $(REPLAY) --recompute

test-council:
	AGENT_PROVIDER=mock $(UV) run python -m pytest tests/council -q

test-confidence-invariants:
	AGENT_PROVIDER=mock $(UV) run python -m pytest tests/council/test_confidence_invariants.py -q

replay-council:
	AGENT_PROVIDER=mock $(UV) run python scripts/replay_council.py --replay $(REPLAY) --recompute

multimodal-perf-smoke:
	cd apps/web && node scripts/perf-smoke.mjs

e2e-replay:
	$(UV) run python -m pytest tests/e2e -q
	cd apps/web && npx playwright test --config playwright.e2e.config.ts

fault-injection:
	$(UV) run python -m pytest tests/faults -q

soak-replay:
	$(UV) run python scripts/soak_replay.py --duration $(DURATION)

hardware-sanity:
	$(UV) run python scripts/hardware_validate.py sanity \
		--rx-a $(shell echo "$(RX_PORTS)" | sed -n 's/.*rx-a=\([^,]*\).*/\1/p') \
		--rx-b $(shell echo "$(RX_PORTS)" | sed -n 's/.*rx-b=\([^,]*\).*/\1/p') \
		--tx $(TX_PORT) --confirmed

calibrate-live:
	$(UV) run python scripts/hardware_validate.py calibrate-live \
		--rx-a $(shell echo "$(RX_PORTS)" | sed -n 's/.*rx-a=\([^,]*\).*/\1/p') \
		--rx-b $(shell echo "$(RX_PORTS)" | sed -n 's/.*rx-b=\([^,]*\).*/\1/p') \
		--tx $(TX_PORT) --confirmed --profile $(PROFILE)

test-hardware:
	$(UV) run python scripts/hardware_validate.py test-hardware \
		--rx-a $(shell echo "$(RX_PORTS)" | sed -n 's/.*rx-a=\([^,]*\).*/\1/p') \
		--rx-b $(shell echo "$(RX_PORTS)" | sed -n 's/.*rx-b=\([^,]*\).*/\1/p') \
		--tx $(TX_PORT) --confirmed --profile $(PROFILE)

compare-live-replay:
	$(UV) run python scripts/hardware_validate.py compare-live-replay --recording $(RECORDING)

release-check:
	$(UV) run python scripts/claim_audit.py
	$(UV) run python scripts/release_audit.py
	$(UV) run python scripts/verify_release.py --mode replay --output artifacts/release_report.json
	$(UV) run python scripts/render_release_html.py --report artifacts/release_report.json --output artifacts/release_report.html
	$(UV) run python scripts/package_release.py --output artifacts/release

package-handoff:
	sh scripts/package_handoff.sh

flash-bundle:
	sh scripts/flash_bundle.sh $(FLASH_ARGS)
