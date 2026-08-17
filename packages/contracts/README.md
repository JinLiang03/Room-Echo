# packages/contracts

Python package `wifi_contracts` — the single structural source of truth for
cross-service messages:

- `NormalizedCsiFrame`, `SourceManifest`
- `FeatureWindow`, `SignalTriplet` (three calibrated proxies)
- `EvidencePacket` (sealed; agents never read raw CSI)
- `AgentClaim`, `AgentChallenge`, `CouncilResult`
- `WebSocketEnvelope`

JSON Schemas in `schemas/` and the web types in
`apps/web/src/generated/contracts.ts` are generated from these models. Run
`make verify-contracts` after any change; never hand-edit generated files.
