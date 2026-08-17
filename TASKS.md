# Tasks

- [x] Phase 01 — scaffold and contracts
- [x] Phase 02 — TX/RX firmware (built, not flashed)
- [x] Phase 03 — collector, mock and replay (live not hardware-validated)
- [x] Phase 04 — deterministic signal pipeline
- [x] Phase 05 — calibration and dataset protocol (simulated workflow; live metrics at Phase 11)
- [x] Phase 06 — three proxy signals and confidence (simulated; live metrics at Phase 11)
- [x] Phase 07 — multi-agent council
- [x] Phase 08 — web experience
- [x] Phase 09 — multimodal output
- [x] Phase 10 — end-to-end integration
- [ ] Phase 11 — live hardware validation (blocked_by_hardware: no boards/ports/room prepared)
- [x] Phase 12 — hardening and handoff (replay release baseline; live blocked)

## Post-release changes

### Competition submission preview — non-final (updated 2026-08-10)

- [x] Same-origin production runtime for Web + REST + WebSocket + MCP
- [x] Public Replay read-only mode with bounded storage and truthful Mock
  provider provenance
- [x] Evaluator-focused two-tool MCP (`get_system_health` +
  `invoke_room_echo`) and a single synchronous `POST /api/agent/invoke`
- [x] One-shot real-provider execution path: compact sealed evidence only,
  full Council orchestration, bounded deadline, process cache, explicit 503/502
  failure, no coupling to the continuously looping Replay
- [x] Mount the seven-Agent viewpoint river on Home, keep one coherent latest
  cycle, and validate 01–07 vertical desktop/mobile rendering
- [x] Unified stream/REST Council runtime and current Replay E2E regression
- [x] Deterministic tracked-source ZIP tooling with manifest, privacy scan, and
  private submission worksheet exclusion
- [x] Current candidate gates: 323 Python passed / 2 credential-gated provider
  smokes skipped, 91 Web tests, type/lint/build, 40 offline browser passed / 2
  size-specific skipped, and 2 service + 10 full-stack Replay E2E
- [x] Push isolated `codex/submission-prep` and open Draft PR #1 for review;
  do not merge to `main` or tag a release until the user confirms the final
  version
- [x] Deploy and externally verify same-origin HTTPS/WSS Preview URL:
  https://wifi-spatial-council-replay.onrender.com — health 200 and both
  evaluator MCP tool calls passed on runtime commit `281e761`, including
  `provider=deepseek`, 10 real calls, `status=ready`, and
  `cycle_status=ambiguous`
- [x] Add the DeepSeek real-provider adapter, strict JSON/Pydantic validation,
  unique call provenance, server-only credential handling, bounded retries,
  cache-before-network behavior, and provider-generic verification tooling
- [x] Add seven-role progressive analysis: concurrent five-role fan-out,
  skeptic/fusion closure, approximately seven-second snapshots, bounded
  Policy-approved continuity, reset semantics, and deterministic timeout
  fallback
- [x] Keep numeric motion/density/depth/quality signal-driven while Fusion may
  select an allowlisted generative theme; bind visible opinions and metadata to
  the exact sealed signal snapshot without mutating measurement or confidence
- [x] Bind DeepSeek output to narrative-only sub-schemas; deterministically
  restore sealed measurement, evidence, role and multimodal fields server-side
  rather than weakening validation after an incomplete first attempt
- [x] Redeploy with the existing server-side Render `DEEPSEEK_API_KEY` and
  verify a credentialed **full Council**: `provider=deepseek`,
  `model=deepseek-v4-flash`, 10 real calls, propose/cross-examine/respond/
  synthesize coverage, MCP cache replay, and confidence cap evidence retained
- [x] Separate technical invocation status (`status=ready`) from semantic
  Council status (`cycle_status=ambiguous` when the sealed evidence warrants
  uncertainty) in REST, MCP smoke validation, and sanitized evidence
- [x] Add a bounded Render Free pre-warm command
  (`scripts/warm_render.py`, `make warm-render`) and document that only a
  paid instance removes platform-level cold starts
- [x] Add typed seven-role presentation semantics: four bounded textual state
  vocabularies, a no-prose five-axis sound projection, explicit skeptic
  sufficiency/pause/validation, and first-person Fusion interaction
- [x] Collapse every same-cycle data observation by default, remove legacy
  `该视角：` prefixes from primary copy, and keep Agent overlays/theme choice
  unable to mutate measurement or confidence
- [x] Replace the thin lower line with a large-number signal-driven river and
  validate exact role headings at desktop/mobile breakpoints
- [x] Split Provider protocol, Mock and OpenAI responsibilities; move shared
  Mock/DeepSeek evidence helpers to a public grounding module; add a current
  documentation index without deleting historical records
- [x] Deploy this seven-role refinement to Render, verify the public MCP tools
  expose the new contracts, and record a fresh real DeepSeek Council proof
- [x] Complete final local static gates and public dynamic MCP measurement:
  health `ok`, protocol `2025-11-25`, `provider=deepseek`, 10 real calls,
  `status=ready`, `cycle_status=ambiguous`, and confidence cap preserved
- [x] Rename the Render service slug to `room-echo` while retaining the Room
  Echo product name and existing public endpoint
- [x] Record J's actual first-use feedback about weak/unchanging Agent voices
  and the resulting component mount/latest-cycle product change
- [x] Obtain J's explicit anonymous-display consent for the person description,
  two quotes and personal need; record the exact text and confirmation time
- [ ] Complete J's public second-use confirmation; do not infer it from tests
- [ ] Confirm final product copy, visuals, team/contact fields, and avatar
- [ ] Freeze the exact approved clean commit, create the final source ZIP, and
  rerun the clean-room install/build/API/WS/MCP/Replay gates from that ZIP
- [ ] Submit and lock the contest version only after explicit user approval

- [x] 2026-08-07 Creative council rework (new themed roles + knowledge bases)
- [x] 2026-08-08 Replay candidate hardening: reconnect hydration, real seek/step,
  dynamic health/latency, raw recording, fail-closed manifests, Home themes,
  release packaging and architecture/MiroFish assessment; full release gate green
- [x] 2026-08-08 Digit inference-field frontend: image-generated design master,
  five character-built spatial themes, signal-driven Canvas morphing, numeric
  Agent assets, Lenis integration, 6.5 s GIF, exact desktop/mobile live
  screenshots, 60 FPS perf evidence, dependency/claim audit, and replay E2E;
  backend contracts unchanged and live hardware explicitly unvalidated
- [x] 2026-08-08 Digit visual revision: pure-white rainbow Home hero with
  denser silhouette and lower information rail, role-specific numeric Council
  glyphs, and a house-shaped Observe signal field; validated with unit/build,
  offline browser, replay E2E, and 60 FPS perf checks
- [x] 2026-08-08 Digit title-mark system: reusable deterministic rainbow numeric
  logos on every h1–h4 chapter heading, lighter art-directed panels, and
  title-specific role/seed marks across all primary views and result cards;
  validated with 58 web tests, typecheck/lint/build, targeted Playwright, and
  clean diff checks
- [x] 2026-08-08 Frameless numeric art direction: removed circular icon frames,
  panel shadows/radii, score-cell boxes, evidence blocks, replay-row chrome,
  and generated-field borders while keeping semantic status accents; validated
  with screenshot inspection and desktop/mobile layout regression
- [x] 2026-08-08 Rainbow information pass: rainbow gradient dividers/metadata,
  rainbow progress tracks, larger Home silhouette, and 4.8 s automatic
  presentation-only theme morphing with reduced-motion fallback; validated
  with 58 web tests, build/lint/typecheck, desktop demo/layout Playwright,
  full replay E2E, and 1440×900 initial/auto-morph screenshots
- [x] 2026-08-08 Home visual cleanup: removed truth-strip and audit-handoff
  copy, returned information typography to dark ink, and replaced the circular
  top-left mark with an irregular rainbow S/C/W lettermark; validated with
  58 web tests, build/lint/typecheck, desktop demo/layout Playwright, and a
  1440×900 screenshot review
- [x] 2026-08-08 Home declutter pass: removed Home status header/stale banner
  and nonessential field, Agent-voice, and theme separator chrome while keeping
  Agent voices, theme selection, and global truth watermark; validated with
  58 web tests, build/lint/typecheck, and 1440×900 screenshot inspection
- [x] 2026-08-08 Agent voice digit parity: mapped each lower Agent viewpoint to
  a deterministic digit stream using the same rainbow palette as the upper
  sensing field, preserving the source claim in `aria-label`; validated with
  58 web tests, build/lint/typecheck, desktop layout Playwright, and a
  1440×900 screenshot review
- [x] 2026-08-08 Agent digit bitmap refinement: removed neon text shadows and
  filled Canvas text masks with dense rainbow digits so viewpoints read as
  numeric word-shapes; validated with 58 web tests, build/lint/typecheck,
  desktop layout 7/7, route navigation, and zero browser console errors
- [x] 2026-08-08 Route comprehension pass: labelled Replay as a sealed-source
  reproducibility tool, rewrote Evidence as readable 250 ms proxy traces,
  expanded Story into a seven-layer soft volume, and compressed Council to
  latest-first with older cycles/details on demand; validated with 58 web tests,
  typecheck/lint/build, desktop layout 7/7, and in-app screenshots
- [x] 2026-08-08 Single-life interaction and IA refinement: three public
  entries, one seven-state signal-driven body, one-time floor-plan/volume/body
  introduction, sustained-event river transitions, pointer/scroll attention,
  source/session-scoped local visual bookmarks, audit-only technical replay,
  explicit unknown body, and truthful role copy; validated with 66 web tests,
  offline Playwright 38 pass / 2 skip, Replay Playwright 10/10, 60 FPS Canvas
  evidence, exact desktop/mobile screenshots, and a regenerated morph GIF
- [x] 2026-08-08 Continuous simulated-life pass: opt-in Replay/Mock looping
  with fresh session ids and Live fail-closed, session-sequence replay fix,
  explicit SIM source badge, functional one-click replay from a running Mock,
  denser 900-digit bodies, and sofa/lamp/non-anthropomorphic presence themes;
  validated with 51 API tests, 77 web tests, 20 desktop/mobile Playwright cases,
  production build, Ruff/mypy, and 60 FPS Canvas evidence

## Never mark complete without evidence

- [x] Replay E2E command and result recorded
- [x] Web screenshots reviewed at desktop and mobile sizes
- [x] Agent-offline fallback demonstrated
- [x] Source disconnect/reconnect demonstrated
- [x] Confidence cap invariant tested
- [x] Unknown-state behavior tested
- [ ] 30-minute live run completed without crash
- [ ] Same-room held-out signal metrics meet gates or are reported as failed
- [x] Final README claims match measured evidence
