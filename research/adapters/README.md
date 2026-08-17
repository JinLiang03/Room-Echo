# Research adapters — open-source comparison records

Per `docs/OPEN_SOURCE_AUDIT.md`, external projects are comparison/adapter
references only; the canonical raw schema and pipeline stay in this repo.
No external parser is merged into the product chain in Phase 04, and no
GPL-3.0 code is copied into these modules.

## Comparison matrix (reviewed 2026-08-06)

| Project | License (per audit) | Input adapter | Role in this repo | Differences from our pipeline |
| --- | --- | --- | --- | --- |
| Espressif esp-csi | Apache-2.0 (target files re-checked) | none needed | Firmware base (Phase 02) | We use binary frames + ring pool; upstream get-started prints CSV in the callback |
| CSIKit | MIT | `csikit_adapter` (research only, not merged) | Parser/visualization comparison | CSIKit normalizes IQ to complex for Intel-style datasets; our canonical CSI is ESP-IDF interleaved int8 and stays ours |
| csiread | MIT | `csiread_adapter` (research only, not merged) | Parsing correctness cross-check | csiread targets Intel/Atheros/Nexmon formats; ESP32 support and field semantics differ from our wire protocol |
| ESPectre | GPL-3.0 | algorithm ablation only (ideas: Hampel, subcarrier selection) | Reference for robust cleaning | Our Hampel/subcarrier logic is re-implemented from the public specification, not copied; no GPL code enters `wifi_sensing` |

## Merge rule

Any adapter that enters a non-research module must first file an
`OpenSourceCandidate` record (per `docs/OPEN_SOURCE_AUDIT.md` §4) with the
exact commit, SPDX license, hardware domain, input adapter, expected gain,
frozen baseline bundle, metric, acceptance delta, and rollback plan, then run
an ablation on the frozen replay before merging.

## Phase 04 decision

Phase 04 validation uses synthetic golden truth (amplitude, carrier indices,
invalid-word handling) and deterministic scenario tests. No external dataset
or checkpoint is used, and no accuracy number from Intel/Nexmon/PicoScenes
projects is attributed to ESP32 hardware.
