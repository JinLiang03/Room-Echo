# Project State

## Current phase

- Phase: 12 — hardening, audit, release & handoff (complete for the replay
  release baseline; live hardware gates remain blocked_by_hardware)
- Status: release_candidate (Replay candidate validated 2026-08-08); live
  pending Phase 11 hardware
- Source mode validated: mock + replay; live implemented with fake-transport
  tests, not hardware validated
- Hardware validated: no

## Replay candidate evidence (2026-08-08)

- `make release-check`: **13 passed / 0 failed / 1 not_run /
  2 blocked_by_hardware**. Python: 264 passed, 1 opt-in OpenAI test skipped;
  contracts: 43 passed; Web: 58 passed; full-stack Replay: 10 passed.
- 60-minute Replay soak: 3638 s, 85 iterations, 0 crashes, bounded queue
  400/400, RSS +2.37%, maximum observed window p95 29.572 ms.
- Browser/performance: offline Playwright 38 passed + 2 redundant screenshot
  cases skipped; multimodal smoke 60 FPS, 156 draw calls, 1 dropped frame,
  303 injected events; fault injection 8/8.
- Replay transport now supports real backward seek and exact paused step;
  discontinuous seeks reset derived state. Snapshot/catch-up restores source
  health, signal history, claims, challenges and final result for late joiners.
- Live now fails closed unless explicit RX-A/RX-B ports, a real topology hash,
  and a matching active recorded non-simulated calibration profile exist.
- Security/release: 11677 claim-audited lines with 0 findings; SBOM contains
  84 Python + 19 Web packages; runtime copyleft flags 0; secret findings 0.
  Public release remains blocked because this project has no chosen LICENSE;
  a private repository is acceptable.
- Deliverables: `docs/ASSESSMENT_2026-08-08.md`,
  `docs/ARCHITECTURE_ALIGNMENT.md`, `artifacts/release_report.{json,html}`,
  and the checksum-verified 2.2 MB source release archive.
- Truth boundary: this evidence qualifies **Replay only**. No ESP32 was
  flashed or measured in this phase; Live stability and held-out metrics stay
  explicitly blocked by hardware.

## Post-release digital-life frontend refinement (2026-08-08)

- Public IA now has only `此刻 / 记忆 / 为什么` plus a small Settings glyph;
  legacy Observe/Evidence/Story/Perf routes remain compatible audit/dev deep
  links, while the normal demo launcher opens `#/home`.
- Home is one 900-digit life rather than seven Agent cards. Its one-time valid
  data introduction is floor plan → same-XY wall lift → signal-selected body;
  later sustained state changes pass through a digit river. Motion, density,
  relative layering, measurement quality, Council disagreement, and unknown
  continue to map only from approved proxy/result fields.
- Presentation mode can now loop an explicitly simulated Mock or Replay source
  with a fresh session id on every pass; Live is rejected before hardware is
  opened. The UI labels these modes `SIM · MOCK` / `SIM · REPLAY`, and manual
  replay resets the old sequence high-water mark before accepting the new
  session. The one-click Memory replay safely stops a different running source.
- The signal-selected body catalogue now includes a wider sofa, offset floor
  lamp, and three-ribbon abstract presence field. The last is deliberately
  non-anthropomorphic and is not a person, pose, identity, furniture, or scene
  detection claim. Active-body visibility rose from 76% to 84% while the
  unknown-state density and activity remain unchanged.
- Local memory stores compact proxy visual bookmarks only, isolated by source
  mode and session; no raw CSI is stored and no memory can change measurement
  or confidence. Technical replay is visible only with audit/debug enabled.
- Validation: API pytest **51/51**, Ruff and API mypy passed; TypeScript passed;
  Vitest **77/77**; lint 0 errors / 5 existing Fast Refresh warnings;
  production build passed; targeted desktop/mobile Playwright **20/20**;
  900-point Canvas perf **60 FPS / 1041 draw calls / 0 dropped frames**;
  responsive in-app browser states were inspected with live Mock events.
- Truth boundary remains Replay-only for this validation. The floor plan and
  bodies are artistic inference-field shells, not WiFi reconstruction of a
  real room or detected furniture; live ESP32 gates remain unvalidated.

## Historical Phase 12 release baseline (2026-08-07; superseded above)

### Release commands (verified)

| Command | Result |
| --- | --- |
| `make setup` | passed (uv sync, contracts/schemas/types/fixtures, npm install) |
| `make demo MODE=replay SCENARIO=walk_through` | passed (autostart demo; also `SCENARIO=demo_2min` and `MODE=mock SCENARIO=interference`) |
| `make test` | passed — 225 pytest + 42 web tests (1 opt-in skip) |
| `make release-check` | passed — claim audit, SBOM/license/security audit, verify_release (13 passed / 0 failed / 1 not_run / 2 blocked_by_hardware), HTML report, source archive + checksum + smoke |

### Phase 12 deliverables

- **Claim review** (`scripts/claim_audit.py`, `artifacts/release/claim_audit.json`):
  9338 lines scanned, 0 findings; exclusions documented (story.ts overreach
  fixtures are controlled and rejected on purpose). User-facing text uses
  proxy language only (verified across README/UI/reports).
- **Policy regression corpus** (`tests/council/policy_corpus.json` + test):
  12 banned phrases each rejected with its exact reason code; negated proxy
  language guaranteed clean (person-count rule extended for “或/和/与人数”).
- **SBOM / license / security audit** (`scripts/release_audit.py`):
  SBOM 74 python + 18 web packages; 0 copyleft flags (GPL/AGPL/LGPL);
  secret scan 0 findings; no CORS middleware (same-origin); derived logs
  contain no keys. Artifacts in `artifacts/release/`.
- **Firmware reproducibility** fixed: `CONFIG_APP_COMPILE_TIME_DATE=n` added to
  both sdkconfig.defaults; three consecutive builds byte-identical:
  `csi_tx.bin` sha256
  `5a8abc38a0e08f9d885a318ab0df8b44a477a6c169201aef0cab87e5a65a767f`,
  `csi_rx.bin` sha256
  `1af2381555750269a1fc4369d8ede4225f7a396b8795db6913971ecfbd19019f`
  (these supersede the Phase 02 non-reproducible hashes; target esp32s3,
  ESP-IDF v5.5.2, esp-csi `8633d671…`, built not flashed).
- **Docs** added: `docs/QUICKSTART.md`, `docs/LIVE_SETUP.md`,
  `docs/CALIBRATION.md`, `docs/DEMO_SCRIPT.md`, `docs/TROUBLESHOOTING.md`,
  `docs/PRIVACY.md`, `docs/LIMITATIONS.md`, `docs/CONTRIBUTING.md`.
- **Release artifacts**: `artifacts/release_report.json` (13/0/1/2),
  `artifacts/release_report.html`, `artifacts/release/sbom.json`,
  `license_audit.json`, `security_audit.json`, `claim_audit.json`,
  `wifi-spatial-council-0.1.0.tar.gz` (4.1 MB) + `.sha256`, smoke verified
  (structure + checksum + 10 modules compiled).

### Known P1 items (owner/impact/workaround)

- Live hardware gates `blocked_by_hardware` (owner: Phase 11 on-site run;
  impact: no live metrics; workaround: replay baseline + mock demo).
- The historical 17.1% soak RSS observation is superseded by the strict
  60-minute 2026-08-08 run (+2.37%, 0 crashes, bounded queue).
- `react-refresh/only-export-components` lint warnings (5) (owner: web;
  impact: cosmetic/HMR; workaround: none needed).
- Mobile still needs progressive disclosure before a polished public demo;
  Replay functionality is not blocked.
- Project-level LICENSE is undecided, so public open-source publication is
  blocked even though the current runtime dependency audit is clean.

## Phase 11 prerequisite findings (2026-08-07, read-only)

Per `prompts/11_HARDWARE_VALIDATION.md`, the prerequisite gate is checked
before any flash/calibration. Findings on this machine:

- Serial devices: only `/dev/cu.Bluetooth-Incoming-Port`, `/dev/cu.debug-console`,
  `/dev/cu.wlan-debug` (macOS system ports) plus one **unconfirmed** serial
  device `/dev/cu.Jinwqc45`. `ioreg` shows no ESP32-class USB identity for it;
  it was NOT probed or flashed (unknown device, one port instead of three).
- Board target/revision: none confirmed; no antennas/power mapping.
- ESP-IDF: v5.5.2 (`30aaf64524299d3bde422ca9a2848090d1bc5d0f`), esp-csi
  `8633d67152db2808f141cc1595970aa9cf406045` (pinned, unchanged).
- Firmware build (ready, NOT flashed): target `esp32s3`,
  `csi_tx.bin` sha256 `f66f414bdd9c2cc2226755845d4ba365ae50b2ea1f1b0b95e7b9fbb10f5072c6`
  (0xb1540), `csi_rx.bin` sha256
  `fed4b348dbf33a13efb664f9a8e446116f866b079ef6e4a1fc133c3025d9d8ee` (0xb39c0).
- Room/topology/5-point depth axis: not prepared; no photos.

Hardware tooling (safe-by-default, refuses without confirmed ports/boards):
- `scripts/hardware_validate.py inventory|sanity|calibrate-live|test-hardware|compare-live-replay`
  — inventory is read-only; every other command exits `blocked_by_hardware`
  unless the three explicit ports exist AND `--confirmed` is given.
- Reports written under `hardware/`: `hardware_inventory.json` (blocked),
  `topology.json` (blocked), `firmware_flash_report.json`,
  `capture_qa_report.json`, `calibration_report.json`,
  `live_acceptance_report.json`, `live_vs_replay_report.json` (all `not_run`
  with reasons).
- Makefile targets: `make hardware-sanity RX_PORTS=… TX_PORT=…`,
  `make calibrate-live PROFILE=…`, `make test-hardware PROFILE=…`,
  `make compare-live-replay RECORDING=…` — verified to refuse
  non-existent/unconfirmed ports (exit 1, blocked).

To unblock: connect three ESP32-S3 boards, confirm each USB serial role
(TX / RX-A / RX-B), record room geometry + 5-point depth axis, then run the
four targets above with `--confirmed`. No metric will be fabricated; until
then all Live gates stay `blocked_by_hardware`.

## Confirmed decisions

- Three-board topology is the target for the final live demo.
- Replay and mock modes are first-class, not temporary hacks.
- Three outputs are calibrated proxies with explicit unknown states.
- Agents never consume raw CSI and never inflate sensor confidence.
- Web rendering and audio remain responsive when the Agent API is offline.
- Pydantic models are the single structural source of truth; JSON Schema and
  TypeScript types are generated and drift-checked (`make verify-contracts`).
- Python is managed with `uv`; `requires-python = ">=3.11,<3.14"` because
  PyArrow has no CPython 3.14 macOS arm64 wheels for the locked line.
- Live serial path stays host-native; Docker is optional, never required.

## Creative council rework (2026-08-07, user-driven)

The debate roles were replaced (sensor data/estimators unchanged):

- Old roles removed from the debate: data_quality / motion / occupancy /
  depth / red_team. New default roles:
  `architecture`, `biota`, `feng_shui`, `psyche`, `soundscape` (proposers) +
  `skeptic` (cross-examiner) + `fusion` (deterministic assembler, kept).
- Every creative claim carries `lens="metaphor"` and a required “(隐喻解读)”
  label; PolicyArbiter rejects unlabeled metaphor claims
  (`unlabeled_metaphor`) and still rejects metric depth, wall presence,
  people, health, fabricated numbers, etc.
- Per-role knowledge bases (`data/knowledge/*.json`) compiled from live web
  research with cited sources: feng_shui (PMC systematic review, Zang Shu,
  Building & Environment HRV/POMS study), architecture (Hall proxemics),
  biota (NeoBiota biosensors, Nature DNA detection), psyche (privacy/
  territoriality, Landscape Online presence), soundscape (Schafer/Truax),
  skeptic (Popper SEP/IEP). Claims embed source URLs in `AgentClaim.sources`.
- Signal-dependent policy rules switched from role names to evidence refs
  (`signals/depth`, `signals/occupancy`) so single-RX/calibration gates still
  hold regardless of which lens references them.
- Call budget default raised 6 → 8 (5 proposers + skeptic + response + fusion);
  demo overreach at cycle-0003 (feng shui “此方位距离 3.2 米,大吉”) and
  blocking challenge at cycle-0004 preserved for the two-minute demo.
- Frontend: Council cards show role color dots for the new personas + a
  “隐喻解读 / 传感器解读” lens badge; generated TS types updated.
- Vivid narrative pass (same session): each persona now speaks in its own
  voice (筑间/蕨/青禾/澄/汐 + 怀疑论者阿古) with deterministic, scenario-flavored
  sentences (e.g. 风水: “此刻的空间像一场缓慢的呼吸:气流静,气局疏朗,明堂落在
  近前…(隐喻解读·青禾)”); the dry `以[concept]视角…可读作…` template is gone.
  `AgentClaim.process` (analysis path) + `sources` (reference URLs) added;
  Council cards render persona glyph/name and a collapsible “来源 · 数据分析
  路径 · 分析过程 · 参考文章” block in small text (hidden by default).

Validation on this rework (targeted):

| Check | Result |
| --- | --- |
| ruff / mypy / verify-contracts | passed (65 files clean, 41 contract tests) |
| council tests | 44 passed + 1 opt-in skip |
| api + faults + e2e | 24 passed (happy replay incl. material challenge, concession, `forbidden_metric_depth` rejection) |
| web lint/typecheck/test/build | passed (42 tests) |
| claim audit / SBOM / license / security | 0 findings / 0 copyleft / 0 secrets |
| Live demo (replay demo_2min) | running with the new roles; claims carry KB source URLs |

Note: the full `make release-check` report was generated before this rework;
the next release cycle should re-run it against the new role set (targeted
gates above are green).

## Analysis-trace upgrade (2026-08-07, user-driven, MiroFish-aligned)

Agent interpretation was upgraded from a one-line conclusion to a visible,
multi-step reasoning trace, modeled on the auditable inference pattern of
the MiroFish swarm architecture (observe -> retrieve -> map -> reason ->
conclude). Sensor data, estimators, and the confidence chain are unchanged;
this is an interpretation-layer only change.

- Contract: `AnalysisStep` added to `packages/contracts` (`step_id`, `phase`,
  `title`, `text`, `evidence_refs`); `AgentClaim` and
  `SpecialistProposal` gain `analysis_steps`. Phase enum is
  `observe/retrieve/map/reason/challenge/conclude` (proposals use the first
  five; the challenge phase is reserved for cross-examination traces).
  JSON Schema, TS types, and fixtures regenerated and drift-checked.
- Mock provider: `_build_analysis_steps` builds the trace deterministically —
  reads only evidence-packet scalars (`motion/occupancy/depth`), retrieves
  concepts from the per-role knowledge bases (`data/knowledge/*.json`),
  maps signal states to persona imagery using each entry's `rule` pairs,
  reasons with role-specific caveats, and concludes with the proposition.
  Same evidence hash + role always yields the same trace.
- Orchestrator: `_claim_from_proposal` propagates `analysis_steps` into every
  `AgentClaim`, so the WS stream and replay fixtures carry the trace.
- Frontend: CouncilView renders the trace as a numbered, collapsible step
  list inside the claim's “来源 · 数据分析路径 · 分析过程 · 参考文章” block;
  each step shows phase badge, title, text, and its own evidence chips.
- Truthfulness: traces still only reference `evidence://` refs, never raw CSI;
  metaphor claims keep the required “(隐喻解读)” label; claim audit 0 findings.

Validation on this upgrade (targeted):

| Check | Result |
| --- | --- |
| ruff / mypy / verify-contracts | passed (65 files clean, 43 contract tests) |
| council + contracts tests | 87 passed + 1 opt-in skip |
| full backend suite | 229 passed + 1 opt-in skip |
| web lint / typecheck / test / build | passed (43 tests) |
| live replay demo (`demo_2min`) | API restarted; all 5 roles emit 5-step traces over WS |
| claim audit | 0 findings (9580 lines) |

## Systematic reading upgrade (2026-08-07, user-driven)

The interpretation layer now produces a *systematic reading* instead of only a
one-line proposition: each claim carries `SystematicReading` with
`headline`, `scene_sketch`, three signal `layers`
(`motion/occupancy/depth` → metaphor + explanation), a persona-voiced
`narrative`, `boundary_notes`, and `multimodal_hints` (extension pointers
for audio/layout/environment/IMU/survey modalities).

- Contract: `ReadingLayer` + `SystematicReading` added to
  `packages/contracts/wifi_contracts/council.py`; `AgentClaim` and
  `SpecialistProposal` gain `systematic_reading`. Schema/TS/fixtures
  regenerated and drift-checked (43 contract tests).
- Mock provider: `_build_systematic_reading` builds it deterministically
  from the same knowledge-base `rule` pairs used by `analysis_steps`;
  per-role scene sketches, narrative openers/closers, boundary notes, and
  multimodal hints are persona-voiced and stable per evidence hash.
- Policy: `PolicyArbiter.scan_text` now also scans every field of
  `systematic_reading` (headline/scene/layers/narrative/boundaries/hints),
  keeping the same forbidden-language guarantees. One regression was caught
  and fixed during dev: “三维重建” in an architecture boundary note triggered
  `forbidden_metric_depth` and was removed.
- Frontend: CouncilView renders a prominent “系统解读” panel — scene sketch,
  three layered reading cards, narrative, boundary notes, and a collapsible
  “多模态延伸提示” block; analysis trace stays in the collapsed details.
- Docs: `docs/DATA_PORTS.md` documents the CSI detection data ports
  (serial → normalized frames → feature windows → triplets → evidence
  packets → WS events) and the reasoning data ports (EvidencePacket in,
  AgentClaim/Challenge/Result out, knowledge base, policy/resolver), plus a
  concrete multimodal extension path.

Validation on this upgrade (targeted):

| Check | Result |
| --- | --- |
| ruff / mypy / verify-contracts | passed (65 files clean, 43 contract tests) |
| council + contracts tests | 89 passed + 1 opt-in skip |
| web lint / typecheck / test / build | passed (44 tests) |
| Playwright full-stack E2E (desktop+mobile) | 4 passed (systematic reading asserted) |
| claim audit | 0 findings (9737 lines) |
| live replay demo | all 5 roles emit 5-step traces + 3-layer readings + 2 multimodal hints each |

## Hardware handoff bundle (2026-08-07, user-driven)

Goal: give a colleague with hardware a bundle that works without re-installing
toolchains (no ESP-IDF, no uv, no Python install; Node.js 18+ still needed for
the Vite dev server).

- Deliverable: `artifacts/handoff/wifi-spatial-council-handoff-<date>.tar.gz`
  — **201 MB** (784 MB uncompressed), produced by `make package-handoff`.
- Content: `.venv` (deps incl. pyserial + esptool), `apps/web/node_modules`,
  a self-contained CPython 3.11.15 arm64 runtime as `.handoff-python/`,
  firmware flash artifacts only (bootloader + app + partition table +
  flash_args + .elf per board; the 148 MB/board of ESP-IDF intermediates are
  excluded), source, fixtures, calibration, docs.
- Excluded (regenerable): `data/derived`, `.mypy_cache`, `.pytest_cache`,
  `artifacts/web` screenshots, `apps/web/dist`, `*.egg-info`, firmware build
  intermediates.
- Colleague steps: extract → `scripts/relink_venv.sh` (re-points venv symlinks,
  `pyvenv.cfg` home, and console-script shebangs at the bundled runtime) →
  `scripts/flash_bundle.sh TX_PORT=... RX_A_PORT=... RX_B_PORT=...` (esptool,
  refuses to guess ports) → run API with `.venv/bin/python -m uvicorn ...` and
  Vite from `node_modules/.bin/vite`.
- Verified end-to-end on a fresh extraction: python 3.11.15 + esptool 4.12.0
  work after relink, `uvicorn` serves `/healthz` 200 from the extracted
  bundle, and `flash_bundle.sh` exits 2 without any port args.
- Dependency note: `esptool>=4.8.0,<5` added to the dev dependency group
  (pyproject.toml) because the handoff machine must flash without an ESP-IDF
  toolchain; the running API session predates this and was not restarted.

## Latest validation

- Phase 01 gate: passed (commands and results below)
- Phase 02 gate: passed (commands and results below)
- Phase 03 gate: passed (commands and results below)
- Phase 04 gate: passed (commands and results below)
- Phase 05 gate: passed (commands and results below)
- Phase 06 gate: passed (commands and results below)
- Phase 07 gate: passed (commands and results below)
- Phase 08 gate: passed (commands and results below)
- Phase 09 gate: passed (commands and results below)
- Phase 10 gate: passed (commands and results below)
- Prompt-pack structural validation: passed (`scripts/validate_prompt_pack.py`)
- Replay end-to-end: passed (service 2/2; full-stack desktop/mobile 10/10)
- Live CSI: pending
- Hardware stability: pending

### Phase 01 gate commands (2026-08-06)

All commands below ran from the repository root with the `uv`-managed
`.venv` (Python 3.11.15). The documented gate commands use `python -m …`;
the equivalent commands here use `uv run python -m …` and are recorded as the
accepted toolchain equivalent.

| Check | Command | Result |
| --- | --- | --- |
| Python lint | `uv run python -m ruff check .` | passed, all checks clean |
| Python types | `uv run python -m mypy services packages` | passed, 15 files, no issues |
| Python tests | `uv run python -m pytest tests/contracts tests/api` | 30 passed |
| Web lint | `npm --prefix apps/web run lint` | passed |
| Web types | `npm --prefix apps/web run typecheck` | passed |
| Web tests | `npm --prefix apps/web run test` | 9 passed (3 files) |
| Web build | `npm --prefix apps/web run build` | passed (vite, 28 modules) |
| Contract drift | `make verify-contracts` | passed (9 schemas, TS types + fixtures, contract tests) |
| Local startup | `make dev MODE=replay` | API :8000 + Web :5173 up; `/healthz` 200 with version/mode/components; Vite proxy to API verified; jsdom tests verify health + offline rendering |

### Phase 02 status (2026-08-06)

Implementation complete and built: `firmware/csi_tx`, `firmware/csi_rx`,
`firmware/shared` (wire protocol, CRC-32, frame pool, counters, build info),
`docs/WIRE_PROTOCOL.md`, `docs/FIRMWARE_SOURCE_REVIEW.md`, Python reference
encoder/decoder, and host-side C tests. The source review pinned esp-csi commit
`8633d67152db2808f141cc1595970aa9cf406045` and ESP-IDF `>=5.5,<6`.

Build environment (auto-discovered by `scripts/build_firmware.sh`):

- ESP-IDF: v5.5.2 at `~/esp/esp-idf-v5.5.2` (git `30aaf64524299d3bde422ca9a2848090d1bc5d0f`)
- Target: `esp32s3` (xtensa toolchain from `~/.espressif`)
- Manifest: `firmware/build/manifest.json`
- Artifacts: `firmware/csi_tx/build/csi_tx.bin` (0xb1540 bytes, 31% app free),
  `firmware/csi_rx/build/csi_rx.bin` (0xb39c0 bytes, 30% app free);
  bootloader ≈ 0x5220–0x5240 bytes. Built with `-Werror`; no compiler warnings.

| Check | Command | Result |
| --- | --- | --- |
| Firmware contract tests | `uv run python -m pytest tests/firmware_contract` | 19 passed (C↔Python golden bytes, CRC known-answer, parser resync: bad magic/version/length/CRC, truncation, oversize, noise bytes, seq wrap, TX payload, frame-pool drop/counter/drain) |
| Python lint (firmware incl.) | `uv run python -m ruff check firmware services packages tests` | passed |
| Firmware build | `make firmware-build` | passed — csi_tx + csi_rx built for esp32s3, manifest + size report written |
| Full regression | `uv run python -m pytest -m "not hardware"` | 49 passed |
| Regression | mypy / ruff `.` / web lint+typecheck+test+build / `make verify-contracts` | all passed |

Phase 02 is marked complete as **built, not flashed / not hardware
validated**: no board was connected and no serial port was guessed.

### Phase 03 gate commands (2026-08-06)

| Check | Command | Result |
| --- | --- | --- |
| Collector tests | `make test-collector` | 36 passed (mock determinism/scenarios, wire round-trip, pairing counters, raw writer atomic publish/incomplete, record→verify→replay equivalence, serial reconnect/epoch, memory bound, frozen fixture, CLI) |
| Fixture generation | `make generate-fixtures` | deterministic, drift-free |
| Replay verify | `make verify-replay REPLAY=data/fixtures/walk_through` | OK — raw 356,000 bytes, status complete |
| Replay smoke | `make replay-smoke REPLAY=data/fixtures/walk_through` | 2000 frames replayed (rx-a/rx-b, seq 0–999) |

Recorded metrics (2026-08-06, this machine):

- Parser throughput: ~324,000 frames/s (2000 frames in 6.2 ms, 512-byte
  chunks) — far above the 100 pps × 2 target.
- Bounded structures: parser buffer ≤ `FRAME_MAX_LEN + 4`; serial outbox
  capped at 10,000; pairer pending bounded by 0.2 s timeout; 10-minute
  synthetic stream (60,000 frames) held tracemalloc current < 100 MB.
- Fixture checksums: `raw.csi.zst`
  `273aba65be5852c164ec19d329147c9db28ea3f10c8342ba4fea791e4192dbe2`,
  `manifest.json` `a0f4f439d4c6b0b10314db9b141a81e09899c33ba470684edfce40f79c835962`.
- Round-trip: mock → record → replay yields NormalizedCsiFrame sequences
  identical except `source_mode` (replay labels frames `replay` by contract).
- Security: malicious manifest/path traversal/absolute path/symlink escape/
  checksum mismatch/missing file/zip-bomb style oversized raw are all
  rejected; incomplete bundles are never verified as complete.
- Live serial: explicit ports only, per-link reader threads, reconnect with
  new epoch + parser reset, fake-transport tests pass; **not hardware
  validated**.

### Phase 04 gate commands (2026-08-06)

| Check | Command | Result |
| --- | --- | --- |
| Sensing tests | `make test-sensing-core` | 24 passed (golden amplitude/index/invalid-word, causal filters no-future, chunk invariance, scenario quality, calibration fit, parquet round-trip, reproducibility, performance) |
| Feature extraction | `uv run python scripts/extract_features.py --replay data/fixtures/walk_through --recompute` | 32 windows from 2000 frames (2.23 s); `features.parquet` + `qa_report.json` written |
| Benchmark | `make benchmark-sensing` | 6000 frames (2×100 pps, 30 s) in 7.07 s → 849 frames/s, 112 windows, max RSS ~50 MB |

Recorded values:

- Feature version: `features-v2` (all cleaning/window/feature parameters live
  in `FeatureConfig`).
- Frozen fixture raw hash:
  `468cac1ffc61db77cc9f87d3c46e5770c27b993c0b3c711dd591ee9ae2ed48e8`
  (walk_through, regenerated when the mock's walk signature was strengthened).
- Feature QA (walk_through, demo profile): 32/32 windows paired; 14/32
  windows carry `interference_high` OOD-quality flags (strong simulated
  motion is not yet separated into the motion signal — that is Phase 06).
- Pipeline design: fit/transform separated (`CalibrationProfile` vs
  `FeaturePipeline`); online Hampel + EMA strictly causal (tested with a
  spike in the last frame); windows never include future frames; chunk
  invariance tested at batch sizes 1/7/1000; single-RX windows emit
  `paired=None` + `single_link` flag and never fabricate pairing.
- Open-source comparison recorded in `research/adapters/README.md`
  (CSIKit/csiread MIT references, ESPectre GPL-3.0 ideas re-implemented,
  no external parser or GPL code merged); ADR 0003 documents why the MVP
  uses no cross-RX phase/AoA/ToF.

### Phase 05 gate commands (2026-08-06)

| Check | Command | Result |
| --- | --- | --- |
| Calibration tests | `make test-calibration` | 22 passed (schema/checksum, trial split, ground-truth isolation, state machine, mock fit reproducibility + held-out metrics, wizard/evaluate E2E, quality precheck) |
| Mock wizard | `uv run python scripts/calibration_wizard.py --mode mock --scenario demo_room_v1 --out data/calibration` | complete — 31 simulated trials, profile + report written |
| Evaluate | `uv run python scripts/evaluate_calibration.py --profile data/calibration/demo_room_v1` | OK — profile checksum verified, held-out metrics re-verified, SIMULATED banner |

Recorded values (simulated, **not hardware evidence**):

- Profile checksum: `sha256:3b557fb6e2dc0b4d5589369a356a6aa6611594b591cb68b53291c7cc187ff0de`
- Held-out metrics: motion separation 0.772553; occupancy ordinal accuracy
  1.0; depth zone accuracy 1.0 (10 held-out trials, one per labeled step;
  deterministic mock is cleanly separable — do not read as real-world skill).
- CalibrationProfile now carries room/board/positions, firmware/feature/
  estimator versions, FitParameters (motion P99/P95 scale, occupancy
  thresholds, depth zone boundaries), trial IDs, metrics, expiry rules,
  checksum, simulated flag, state. Demo source is forced `simulated=true`;
  tampered checksums are rejected by evaluate.
- Trials: one raw bundle per trial; labels only in `ground_truth.json`
  (never in raw/events/features; replay ignores the file); trial-level
  stratified train/validation/test split (warmup excluded); randomized
  recording order; old profiles never overwritten (writer refuses).
- Quality precheck gates low packet coverage / insufficient carriers and
  triggers one re-record in the wizard.

### Phase 06 gate commands (2026-08-06)

| Check | Command | Result |
| --- | --- | --- |
| Signal tests | `make test-signals` | 17 passed (motion idle/walk + single-link, occupancy ordinal + motion freeze, depth monotonic + single-RX unknown + mismatch uncalibrated, quality gate packet-loss/interference/stale, invariants property tests, evidence sealing) |
| Replay signals | `make replay-signals REPLAY=data/fixtures/walk_through RECOMPUTE=1` | 33 triplets, 3 evidence seals, QA report written |
| Inspect | `uv run python scripts/inspect_signals.py --replay data/fixtures/walk_through --report artifacts/signal_qa.html` | SIMULATED banner, deterministic triplets + hashes |

Recorded values (simulated, **not hardware evidence**):

- Estimator version: `signals-v1/estimator-v1/features-v2`; fixture raw hash
  `468cac1ffc61db77cc9f87d3c46e5770c27b993c0b3c711dd591ee9ae2ed48e8`.
- walk_through replay: motion ramps micro_motion→moving→fast_change and back;
  occupancy is `low` when quiet and `unknown` during fast motion (motion is
  never read as density); depth `near` (fixture has no depth gradient);
  statuses ok=13 / insufficient_signal=20; final stale triplet clears all
  state (unknown, confidence 0).
- Evidence: example sealed hash
  `sha256:8ed6373e13b9ac70e333a6ce907fcf462950c2827bc6e6ad55ecdc248d6bf2dd`
  (deterministic; same window+profile → same hash; arrays never embedded,
  evidence index holds scalars only; audit log append-only).
- Quality gate: conservative min per signal; `signal_confidence <=
  signal_quality`, `sensor_confidence_cap = min(required qualities)`,
  unknown → confidence 0 (property-tested; ADR 0004). Agent fields are
  absent from the estimator dependency graph (tested).
- Unknown/degraded behavior verified: single RX → depth always unknown and
  occupancy unknown (dual-link training); profile/topology mismatch →
  uncalibrated; 40% packet loss → degraded within two windows; staleness
  clears previous state with zero confidence.

### Phase 07 gate commands (2026-08-06)

| Check | Command | Result |
| --- | --- | --- |
| Council tests | `AGENT_PROVIDER=mock make test-council` | 42 passed, 1 skipped (opt-in OpenAI smoke, not in CI) |
| Replay council | `AGENT_PROVIDER=mock make replay-council REPLAY=data/fixtures/walk_through` | 3 evidence seals; 2 committed cycles; status supported=1/unavailable=1; no policy rejections; report `artifacts/council_qa.html` |
| Confidence invariants | `AGENT_PROVIDER=mock make test-confidence-invariants` | 5 passed |
| Full regression | ruff / mypy / pytest / web lint+typecheck+test+build / `make verify-contracts` | all passed — 207 passed, 1 skipped, mypy 62 files clean, web 9 tests, 15 schemas, 41 contract tests |

Recorded values (mock provider, simulated — **not hardware evidence**):

- Providers: `MockAgentProvider` (`mock-council.v1` templates, fixed seed
  `0xC011EC1`) + `OpenAIAgentProvider` (server-side key only; model from
  `AGENT_COUNCIL_MODEL`/config, default `gpt-4o-mini`; health probe; opt-in
  smoke `COUNCIL_OPENAI_SMOKE=1`).
- Prompt registry: 6 roles (`data_quality`/`motion`/`occupancy`/`depth`/
  `red_team`/`fusion`), version `council-prompt.v1`, per-role sha256 hashes
  (e.g. motion `13cfa53b…`, fusion `06a5ce4f…`); common prompt + role
  increments follow `AGENT_COUNCIL.md` §7.
- Policy: deterministic `PolicyArbiter` (`policy-v1`) with 15+ reason codes;
  severity floors (confound/missing_evidence/contradiction → material;
  calibration_mismatch/causal_overreach/stale_evidence → blocking);
  unresolved penalties `material_penalty=0.75`, `blocking_penalty=0.5`.
- Confidence chain: `model_support = min(motion/occupancy/depth confidence)`;
  1/3/6-agent runs, 100% agreement, and 10× repeated evidence all keep
  `display_confidence` identical; `display <= model_support <= cap` property
  tested (Hypothesis). Agent count/agreement never enter the formula.
- Debate: default budget 6 attempts/cycle — walk_through cycle-0001 used
  exactly 6 calls (4 propose + red_team cross-examine + 1 respond), fusion
  deterministic; with budget 8 the full 7-call debate including provider
  Fusion runs. Example cycle evidence hash (unchanged from Phase 06):
  `sha256:8ed6373e13b9ac70e333a6ce907fcf462950c2827bc6e6ad55ecdc248d6bf2dd`;
  display/model/cap all 0.838183; claims 4, challenges 1 (info confound,
  resolved), rejections 0.
- Mock behavior verified: single-RX depth abstains; interference produces a
  material confound targeting the motion claim; controlled bad-output modes
  (bad refs, old hash, overreach, fabricated numbers) are rejected by policy
  with stable reason codes.
- Scheduler: one active cycle + one latest pending slot (intermediate cycles
  dropped by design); sequence-guarded commits (stale cycles cannot overwrite
  newer snapshots); retry-once on timeout; 15 s hard deadline yields an
  audited degraded baseline; all-provider-offline yields deterministic
  “讨论不可用” result.
- API: `GET /council/health|usage|cycles|cycles/{id}[/claims|challenges|rejections]`;
  responses never contain credentials or absolute paths (tested).
- Audit: append-only JSONL at `data/derived/council/{session}.audit.jsonl`;
  per-cycle `CouncilCycleDetail` (claims, challenges, rejections, calls,
  result) retained in the in-memory store; ADR 0005 records the design.

### Phase 08 gate commands (2026-08-07)

| Check | Command | Result |
| --- | --- | --- |
| Web lint | `npm --prefix apps/web run lint` | passed, 0 errors (5 react-refresh warnings: non-component exports in `state.tsx`) |
| Web types | `npm --prefix apps/web run typecheck` | passed |
| Web tests | `npm --prefix apps/web run test` | 28 passed (8 files: reducer, WS client, signal cards, council, replay, app shell, contracts, health) |
| Web build | `npm --prefix apps/web run build` | passed (vite, 48 modules, 192 KB JS / 15 KB CSS) |
| Web E2E | `npm --prefix apps/web run test:e2e` | 18 passed (9 specs × desktop 1440×900 + mobile 390×844, channel=chrome) |
| Live API+WS smoke | uvicorn + python websockets client | snapshot/signal.frame/quality.update/cycle.started/agent.claim/synthesis.result flow with monotonic sequences; REST bundles/start/control/stop OK |
| Python regression | ruff / mypy / full `pytest -m "not hardware"` / `make verify-contracts` | all passed — 215 passed + 1 skipped, mypy 65 files clean, 41 contract tests |

Recorded values:

- Screenshots (viewed via E2E layout assertions; saved for human review):
  `artifacts/web/desktop-{observe,story-moving,council-rejected,evidence,story-single-rx}.png`
  (1440 px wide) and `artifacts/web/mobile-{...}.png` (390 px wide). Layout
  assertions at both sizes: no horizontal overflow, all `.panel` bounding
  boxes inside the viewport, mobile signal cards single-column (>80% width).
- Backend stream: one session at a time; `ReplayFrameSource` pacing at
  0.25–4×; WS snapshot + bounded ring buffer (400 events) + `last_sequence`
  catch-up; out-of-order/duplicate events dropped client-side and counted
  (`dropped` in debug settings); sequence monotonicity asserted in tests.
- UI honesty verified: offline shows stale overlay + placeholder values
  (never last value residue); paused/finished show explicit stale overlay;
  Council shows “讨论不可用” instead of loading forever; ground truth
  hidden by default and labeled as evaluation-only; watermark
  `INFERENCE FIELD — NOT A CAMERA IMAGE` on every page; measured/inferred/
  generated/simulated legend permanent.
- Demo route `#/story` renders 8 fixed states (idle/moving/interference/
  single_rx/unknown/ambiguous/timeout/rejected) from generated fixtures;
  keyboard navigation and reduced-motion toggle verified in E2E.

### Phase 09 gate commands (2026-08-07)

| Check | Command | Result |
| --- | --- | --- |
| Web tests | `npm --prefix apps/web run test` | 42 passed (10 files: multimodal mapping, soundscape engine, reducer, WS, cards, views, shell) |
| Web E2E | `npm --prefix apps/web run test:e2e` | 32 passed (16 specs × desktop/mobile; five-state sculpture, pixel-level dimness, no-`<img>` checks, keyboard nav) |
| Web build | `npm --prefix apps/web run build` | passed (208 KB JS / 16.75 KB CSS, gzip 65/4 KB) |
| Perf smoke | `make multimodal-perf-smoke` | passed — 61 FPS, 156 draw calls, 0 dropped visual frames, 303 events/10s @30Hz, audio node count 10 stable; report `artifacts/web/perf-smoke.json` |
| Lint/typecheck | `npm --prefix apps/web run lint` / `typecheck` | 0 errors (8 react-refresh warnings) / clean |

Recorded values (mapping `multimodal-v1`):

- Exact baseline mapping implemented: particle_speed=lerp(0.08,1.8,motion),
  pulse_hz=lerp(0.12,2.4,motion), field_density=occupancy probability
  weighted, z_layer_separation=depth ordinal weighted, saturation=
  lerp(0.2,1.0,measurement_quality), edge_diffusion=1−quality,
  disagreement_phase=bounded agreement-only (never touches signal values).
- Determinism: `mulberry32(VISUAL_SEED=0x5eed)` particles; same seed/input
  ⇒ identical params + render snapshot hash (unit + E2E). NaN/Infinity
  guarded via `safeMin`/`clamp01`.
- Unknown/stale: activity eases to 0, layers collapse, dim static haze;
  E2E pixel sample shows unavailable flat (stddev < 0.7× walk) and dim
  (5 < mean < 160); no residual previous state.
- Audio: gesture-gated `SoundscapeEngine` + Web Audio graph (motion→tempo,
  occupancy→filter/harmonics, depth→stereo width+delay, quality→clarity);
  default muted; blur/pause/stop fade out; 2000-update unit test with stable
  node count; real graph measured 10 nodes stable in smoke.
- Five-state screenshots (idle/walk/degraded/ambiguous/unavailable) saved as
  `artifacts/web/desktop-state-{...}-1440.png` and
  `artifacts/web/mobile-{...}-390.png` (mobile also `mobile-state-*`);
  watermark present on every page; ADR 0006 records the Canvas-2D-over-WebGL
  decision, determinism, audio lifecycle, and perf measurement contract.

### Phase 10 gate commands (2026-08-07)

| Check | Command | Result |
| --- | --- | --- |
| Full tests | `make test` | passed — 225 passed + 1 opt-in skipped (full `pytest -m "not hardware"` + 42 web tests) |
| Replay E2E | `make e2e-replay` | passed — service-layer happy replay on `demo_2min` (raw→features→signals→evidence→debate→policy→result, claims/material challenge/concession/`forbidden_metric_depth` rejection) + full-stack Playwright (real API + Web, 4 specs × desktop/mobile) |
| Fault injection | `make fault-injection` | 8 passed — packet_loss/single_rx/tx_stale/profile_mismatch/llm_timeout/invalid_json/disk_error/sequence monotonicity |
| Soak | `make soak-replay DURATION=60m` | passed — 59 iterations (~60 min), 0 crashes, max queue 400 (bounded at BUFFER_LIMIT), RSS peak growth 17.1% (recorded warning; `ru_maxrss` monotonic high-water) → `artifacts/web/soak_replay.json` |
| Release verify | `python scripts/verify_release.py --mode replay --output artifacts/release_report.json` | 13 passed / 0 failed / 1 not_run (live-30min) / 2 blocked_by_hardware (hardware inventory + same-room metrics); `release_candidate: true` → `artifacts/release_report.json` |
| One-click commands | `make demo MODE=replay SCENARIO=walk_through` · `SCENARIO=demo_2min` · `MODE=mock SCENARIO=interference` · `make dev MODE=live RX_PORTS=…` | verified — autostart demo session on API boot; mock start/stop REST smoke OK; live requires explicit ports and stays `blocked_by_hardware` until Phase 11 |

Recorded values:

- 2-minute frozen fixture `data/fixtures/demo_2min` (120 s, 24 000 frames,
  ~1.2 MB zstd): scripted timeline idle → far entry → approach → occupancy
  change → ambiguous interference → recovery, ramped parameters for stable
  estimator states; demo seals every 12 s of demo time so the council runs
  each cycle (scheduler keeps one active + latest pending).
- Demo council behaviors verified in-fixture: 4 specialist claims,
  red-team material confound (interference window, `interference_high` flag
  now sealed into the EvidencePacket), revision/concession (blocking
  challenge at cycle-0004), Policy rejection (`forbidden_metric_depth`,
  controlled demo overreach at cycle-0003), Fusion results with honest
  `display_confidence <= model_support <= sensor_confidence_cap`.
- Session API: `/api/stream/start?mode=replay|mock|live&bundle_id=&scenario=&demo=`,
  idempotent same-source start, 409 on different source while running,
  `/control` (pause/resume/step/seek/rate/record/start/stop), `/faults/{name}`,
  `/metrics` (window latency p50/p95/p99, event rate, queue depth),
  `/status` (session_id/mode/source/demo_phase/faults), `/stop` idempotent.
- Observability: per-session NDJSON event log
  `data/derived/stream/{session_id}.events.jsonl` (full WS event stream),
  structured `StreamStatus`/metrics; no secrets or raw MACs; latency metrics
  recorded server-side (signal→WS); UI p50/p95/p99 from web perf harness.
- Fault injector: 8 deterministic faults with REST control + pytest suite;
  `_TimeoutProvider` and misbehaving-mock provider swap are runtime-only.
- Soak: 59 demo_2min iterations, 0 crashes, queue bounded at 400 events,
  total ~12 300 events per iteration; RSS peak growth 17.1% recorded as a
  deviation from the <10% target (monotonic high-water, warm-up dominated).
- Operator tooling: `scripts/run_demo.py` (preflight/start/URL/progress/stop/
  artifacts), `scripts/verify_release.py` (release_report.json with
  passed|failed|not_run|blocked_by_hardware), `README-OPERATOR.md`.

## Post-release digit inference-field frontend (2026-08-08)

- Added a light, default `#/home` experience without changing the API, WebSocket
  contract, estimators, calibration, Evidence, or Council orchestration. The
  page consumes the existing `StreamProvider` triplet/history/result state.
- `digit-field-v1` renders five deterministic, user-selected character themes
  (lounge/studio/passage/garden/atrium) in one Canvas 2D. Motion, occupancy
  proxy, relative depth proxy, quality, and disagreement use the existing
  `multimodal-v1` scalars; theme and pointer interaction are presentation-only.
- Unknown/stale clears every signal-driven parameter and all Council readouts,
  while retaining an explicitly labelled static user-theme preview. Current
  measurement quality is separated from the matched `CouncilResult` sensor cap
  and final claim; the browser E2E asserts final claim <= its result cap.
- Added numeric Agent sigils (`01/37/08/22/56/?/Σ`), native radio semantics,
  reduced-motion/static redraw, visibility pause, DPR cap 2, and responsive
  desktop/mobile layouts. `lenis@1.3.26` (MIT) is the only new production
  dependency and does not enter the stream, Canvas, or audio data paths.
- Design and review artifacts:
  `artifacts/design/digit-inference-field-homepage-v1.png` (1536×1024),
  `artifacts/design/digit-field-morph.gif` (6.5 s, 65 frames),
  `artifacts/web/desktop-home-digit-field-live.png` (1440×900), and
  `artifacts/web/mobile-home-digit-field-live.png` (390×844). The design prompt
  is stored beside the PNG; every visualization is labelled as a concept/
  inference field and not camera or sensor output.

Validation evidence:

| Check | Result |
| --- | --- |
| Web lint/type/unit/build | passed — 0 lint errors (5 existing fast-refresh warnings), strict TypeScript, 58 Vitest tests, production build 82.47 kB JS gzip |
| Offline browser E2E | passed — 38 desktop/mobile tests, 2 viewport-specific screenshot cases intentionally skipped; unknown/stale, layout, keyboard, and reduced-motion paths covered |
| Replay full-stack E2E | passed — 2 Python replay E2E + 10 Playwright desktop/mobile tests, including Home triplet intake, pointer/theme signal immutability, result-cap invariant, late join, and seek/step |
| Python full gate | passed — Ruff, mypy (65 files), 264 non-hardware tests in the final release verifier; 1 credential-gated OpenAI smoke skipped by design |
| New renderer perf | passed — 480 glyphs, active morph + pointer, 60 FPS, 525 draw calls, 0 dropped frames (`artifacts/web/digit-field-perf.json`) |
| Existing renderer perf | passed — 60 FPS, 156 draw calls, 1 dropped frame, stable 10 audio nodes (`artifacts/web/perf-smoke.json`) |
| Claim/security/license | passed — 0 claim findings, 0 secrets, clean logs, 0 copyleft runtime flags; Lenis recorded as MIT in SBOM |
| Repository release verifier | passed — 13 passed / 0 failed / 1 not run / 2 blocked by hardware; `release_candidate: true` in `artifacts/release_report.json` |

Public publication remains **not ready** because the repository still has no
project-level `LICENSE`; standalone GPLv2+ `esptool` also remains explicitly
flagged for tooling review. These are repository-wide release prerequisites,
not failures of the frontend runtime audit. Live ESP32 validation remains
blocked by hardware and is not claimed.

## Active blockers

- Exact ESP32 board revisions, antenna type, room geometry, and serial port names must be recorded during phase 11.

## Unresolved warnings

- FastAPI `TestClient` emits a `StarletteDeprecationWarning` about
  `httpx`/`httpx2` (upstream fastapi package); tests still pass.
- OpenAI provider integration is opt-in (`COUNCIL_OPENAI_SMOKE=1` + server
  key); not run in default CI. No key present on this machine → provider
  health `degraded` with mock/baseline fallback.
- `react-refresh/only-export-components` warnings (5) in `lib/state.tsx`
  (exports reducer/context next to the provider); cosmetic, lint passes.
- Alert tray is fixed bottom-right and not dismissible; fine at both target
  sizes but could overlap long content on very small screens.
- Stale overlay `top` is tuned for the desktop topbar; on a wrapped mobile
  topbar it may sit lower than ideal (no overflow, verified).
- Renderer is Canvas 2D by design (ADR 0006); a future WebGL upgrade would
  swap behind the same `RenderParams` interface. Headless perf measured
  60 FPS; if a target machine falls below 60 the smoke records an explicit
  fallback instead of failing silently.
- Phase 09 screenshots were originally validated programmatically; the new
  Home artifacts were additionally inspected visually at exact 1440×900 and
  390×844 target viewports on 2026-08-08.
- The historical 17.1% RSS high-water and transient sensing benchmark warning
  are superseded by the strict 60-minute soak (+2.37%, 0 crashes) and the
  vectorized causal Hampel regression/benchmark in the final release gate.
- Phase 11 is blocked: the three-board prerequisite is not met on this
  machine (one unknown serial device only). Nothing was flashed; no Live
  claim is made.
- No git repository exists in this directory yet; initialize one when version
  control is wanted.
- `make dev` uses `make -j2`; Ctrl-C stops both processes (verified).

## Change log

- 2026-08-08: Added the post-release `digit-field-v1` Home experience —
  image-generated design master, five deterministic numeric themes, Canvas 2D
  morph/pointer interaction, numeric Agent sigils, matched confidence display,
  Lenis scrolling, GIF + desktop/mobile live screenshots, dedicated 60 FPS
  perf smoke, open-source/ADR/UX docs, and full replay/browser gates. Backend
  and sensing contracts unchanged; live hardware remains blocked.
- 2026-08-08: Revised the digit frontend visual system — pure-white canvas,
  deterministic rainbow digits, denser/larger Home silhouette with all
  explanatory copy and signal rail below the hero, role-specific static Agent
  digit glyphs in Council, and a Canvas-2D house-shaped Observe field. The
  generative labels remain explicit inference metaphors, and the Story route
  keeps the legacy sculpture for its state regression corpus. Validation:
  web unit 58 passed, lint 0 errors (5 existing refresh warnings), build
  passed, offline Playwright 38 passed / 2 intentional skips, replay E2E
  2 pytest + 10 Playwright passed, digit perf 60 FPS / 585 draws / 0 drops.
- 2026-08-08: Added the reusable rainbow digit title-mark system across every
  h1–h4 section in Home, Observe, Council, Evidence, Replay, Story, Settings,
  Perf, result cards, signal cards, and error fallback. Chapter panels were
  visually lightened (no heavy radius/shadow/right frame) so the deterministic
  numeric marks carry the visual hierarchy. Validation: 58 web tests passed,
  typecheck/lint/build passed, and targeted desktop/mobile Playwright passed
  22 tests with 2 intentional skips; `git diff --check` is clean.
- 2026-08-08: Removed the remaining decorative frame chrome from the numeric
  marks and primary content field: marks are now transparent, borderless
  glyphs; cards, score cells, evidence blocks, replay rows, and generated
  fields are frameless with only semantic status accents retained. Validation:
  typecheck/lint/build passed, 58 web tests passed, desktop screenshot/layout
  Playwright passed 16 tests with 2 intentional skips, and screenshots were
  visually inspected at 1440×900.
- 2026-08-08: Added rainbow information ink and rainbow divider rules to the
  shell, Home metadata, readouts, evidence/replay details, and progress tracks;
  enlarged the Home digit field and enabled a 4.8 s presentation-only theme
  morph cycle (reduced-motion stays static). Validation: typecheck/lint/build,
  58 web tests, 10 desktop Playwright demo/layout tests, full replay E2E
  (2 pytest + 10 Playwright), and initial/auto-morph Home screenshots inspected
  at 1440×900; backend contracts unchanged.
- 2026-08-08: Refined Home per visual review — removed the two residual
  explanatory text bands (truth strip and audit handoff), restored information
  typography to dark ink while retaining rainbow divider rules, and replaced
  the circular brand dot with an irregular S/C/W rainbow lettermark. Validation:
  typecheck/lint/build, 58 web tests, desktop demo/layout Playwright 10/0,
  screenshot inspected at 1440×900, and `git diff --check` clean.
- 2026-08-08: Final Home declutter pass — removed the Home status header and
  Home-only stale banner, then removed field/voice/theme separator chrome while
  keeping the Agent voice river, theme selector, and global truth watermark.
  Validation: typecheck/lint/build, 58 web tests, and 1440×900 screenshot
  inspection; other routes retain their status overlays.
- 2026-08-08: Matched the lower Agent voice river to the upper sensing field:
  each sealed viewpoint is now rendered as a deterministic rainbow digit stream
  using the shared palette, while the original claim remains available through
  its accessible label. Validation: typecheck/lint/build, 58 web tests,
  desktop layout Playwright passed, and the 1440×900 Home screenshot was
  inspected; local API-backed offline assertion was not used as a visual gate.
- 2026-08-08: Clarified secondary routes without removing audit affordances:
  TopBar now exposes route context, Replay opens with a concise sealed-source
  explanation, and Evidence replaces ambiguous curves with three labelled
  250 ms proxy traces (older → latest, 0–1) plus explicit interpretation
  boundaries. Validation: typecheck/lint/build, 58 web tests, and desktop
  layout Playwright 7/7.
- 2026-08-08: Made Story's signal sculpture read as a soft spatial volume:
  seven translucent perspective layers, ribs, drifting low-alpha volume blobs,
  and numeric particles are driven by the existing render parameters only;
  the visible label and aria text retain the inference-field/not-camera limit.
  Council now defaults to the latest cycle, collapses older cycles and long
  narrative/claim-boundary blocks, and keeps the Agent digit atlas as the
  visual index. Validation: typecheck/lint/build, 58 web tests, desktop layout
  Playwright 7/7, and in-app Story/Evidence/Council screenshot inspection.
- 2026-08-08: Replaced the Agent digit stream with a no-glow Canvas bitmap:
  the accessible claim text is used only as a mask and every visible mark is a
  dense rainbow digit, making the lower rail read as words assembled from
  numbers rather than random substitutions. Validation: typecheck/lint/build,
  58 web tests, desktop layout Playwright 7/7, Home→Observe→Home navigation,
  and browser console inspection with zero runtime errors.
- 2026-08-07: Creative council rework — debate roles replaced with
  architecture/biota/feng_shui/psyche/soundscape + skeptic; web-researched
  knowledge bases with cited sources; `lens` + `sources` on claims;
  `unlabeled_metaphor` policy rule; refs-based single-RX/calibration gates;
  budget 8; Council UI lens badges; all targeted gates green.
- 2026-08-07: Phase 12 completed — claim audit (0 findings), policy
  regression corpus, SBOM/license/security audit, reproducible firmware
  builds (compile-time date disabled; byte-identical across 3 builds),
  8 handoff docs, `make release-check` (verify_release 13/0/1/2 + HTML +
  archive/checksum/smoke), release candidate recorded; live gates stay
  blocked_by_hardware.
- 2026-08-07: Phase 11 prerequisite gate executed — read-only inventory
  found no confirmed ESP32 boards (1 unknown serial device only); firmware
  build hashes recorded, hardware tooling + blocked reports written under
  `hardware/`; Phase 11 marked `blocked_by_hardware` in STATE and release
  report (13 passed / 0 failed / 1 not_run / 2 blocked_by_hardware).
- 2026-08-07: Phase 10 completed — replay/mock/live unified stream session
  (session_id, autostart, demo phase labels), scripted `demo_2min` frozen
  fixture + demo-seal cadence, demo council behaviors (material challenge,
  concession, policy rejection, fusion), session API with idempotency/errors/
  metrics/faults, per-session event log, fault injector + 8 tests,
  service-layer + full-stack Playwright E2E, 60-minute soak, `run_demo.py`,
  `verify_release.py` + release_report.json (13/0/1/1, candidate true),
  README-OPERATOR.md.
- 2026-08-07: Phase 09 completed — `multimodal-v1` deterministic mapping +
  seeded particles, Canvas 2D signal sculpture (depth rings, particle field,
  disagreement phase rings, unknown/stale collapse), `SoundscapeEngine` +
  Web Audio graph (gesture-gated, muted default, blur fade, bounded nodes),
  ResultCard (headline/three signals/three quality dims/alternatives/
  limitations/hash/versions/watermark), `#/perf` harness + perf smoke
  Makefile target, five-state E2E screenshots + pixel checks, ADR 0006.
- 2026-08-07: Phase 08 completed — design-token CSS system; app shell with
  hash routing, ErrorBoundary, session store reducer, WS client
  (reconnect + sequence recovery + out-of-order counting), topbar
  (mode/session/RX/channel/calibration/freshness/Start-Pause-Stop-Record),
  Observe/Council/Evidence/Replay views, settings (mute/reduced-motion/
  contrast/debug/ground-truth/export), story demo route with 8 fixed states,
  permanent watermark + legend, stale overlays; backend replay stream
  session + WS hub + REST replay/stream endpoints + `quality.update` events;
  Playwright E2E (18) + screenshots; 28 web tests; live API+WS smoke passed.
- 2026-08-06: Phase 07 completed — AgentProvider protocol with
  MockAgentProvider + OpenAIAgentProvider (OpenAI Agents SDK structured
  outputs), versioned/hashed prompt registry, six roles, deterministic
  PolicyArbiter with reason codes and severity floors, orchestrator state
  machine (seal→gate→propose→cross-examine→respond→policy→synthesize→commit),
  call budget 6 + retry-once + 15 s deadline, one-active-one-pending
  scheduler, sequence-guarded store, append-only audit log, Fusion with
   deterministic fallback, replay-council CLI + QA HTML, council API routes,
  ADR 0005, 207 total tests passing (43 council, 1 opt-in smoke skipped).
- 2026-08-06: Phase 06 completed — motion/occupancy/depth estimators,
  conservative QualityGate (ADR 0004), SignalEstimator with confidence
  invariants, EvidenceTrigger (cooldown/stable-change/major-transition),
  sealed compact EvidenceBuilder + append-only audit log, inspect-signals
  CLI with QA HTML + model card, demo profile gained demo fit parameters,
  mock interference redesigned as correlated drift + packet loss,
  17 signal tests, 148 total tests passing.
- 2026-08-06: Phase 05 completed — CalibrationProfile signing (checksum,
  expiry, match score/hard invalidation), calibration state machine,
  trial recording with ground-truth isolation, stratified trial split,
  baseline estimators (motion scale, occupancy ordinal, depth zones),
  wizard + evaluate CLI + `wsc-calibration`, JSON/HTML reports, mock
  simulated calibration (simulated=true enforced), 22 calibration tests,
  131 total tests passing.
- 2026-08-06: Phase 04 completed — cleaning (validate, first-word, IQ→dB,
  common-mode centering, causal Hampel+EMA), 2 s/250 ms windows, per-link +
  paired features, CalibrationProfile fit/demo, FeatureWindow contract
  extension (quality + paired + 4 new link fields), parquet IO, extract CLI,
  benchmark, ADR 0003, research adapter records, 24 sensing tests.
- 2026-08-06: Phase 03 completed — MockFrameSource (6 scenarios), serial
  parser (wsc_wire), dual-link pairing, append-only raw bundles (zstd,
  atomic publish, incomplete marker), replay verifier + source (virtual
  clock/seek/step), SerialLiveFrameSource (reconnect/epoch), recorder, CLI,
  frozen `data/fixtures/walk_through` bundle, 36 collector tests, ADR 0002.
- 2026-08-06: Phase 02 completed — csi_tx/csi_rx built with ESP-IDF v5.5.2
  (esp32s3, -Werror clean), shared wire protocol + CRC-32 + frame pool +
  counters, docs/WIRE_PROTOCOL.md, source review record, Python reference
  codec, 19 host tests passed, build manifest + size report recorded. Built,
  not flashed.
- 2026-08-06: Phase 01 completed — monorepo skeleton, Pydantic contracts
  (9 models), generated JSON Schemas + TypeScript types + typed TS fixtures,
  deterministic mock fixtures, FastAPI `/healthz`, React/Vite/TS web shell,
  Makefile targets, ADR 0001, local dev docs.
- 2026-08-06: Created the complete phased prompt specification.
- 2026-08-06: Validated 12 phases plus master, 26 Markdown files and two JSON schemas.
