# Privacy

- Raw CSI never leaves the server. Agents receive only sealed, compact
  `EvidencePacket` objects; arrays and raw frames are not in agent inputs.
- Ground truth never enters packets, prompts, or traces; the UI hides it by
  default and labels evaluation mode explicitly.
- Logs record model/latency/status/usage and evidence hashes — never API keys,
  real MACs, or raw CSI (tested).
- API keys are server-side environment only; the browser never receives them
  (`/council/health` is a presence probe, not a credential).
- Data locations: `data/raw` for local append-only captures,
  `data/derived/{evidence,council,stream,features}` for derived records, and
  `data/fixtures` for deterministic demo data. Delete the relevant directories
  to remove captured data; raw bundles carry a privacy declaration in their
  manifest.
- Release and hardware handoff packages exclude `data/raw` by default. Export
  a selected verified bundle separately only when the recipient and retention
  policy are explicit.
- Automatic retention/deletion is not implemented in this checkout. Operators
  must review and remove expired bundles from `data/raw` explicitly; there is
  no environment flag that silently deletes sensor data.
- Every page shows `INFERENCE FIELD — NOT A CAMERA IMAGE` and the
  measured/inferred/generated/simulated legend.
