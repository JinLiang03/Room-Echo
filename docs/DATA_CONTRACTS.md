# 数据契约

## 1. 设计原则

- 每个对象都有 `schema_version`、Session、时间和来源模式。
- Raw 是不可变事实；Feature 和 Signal 可重算；Agent 是可审计解释。
- JSON 用于控制面和 API；NDJSON/Zstd 用于事件与 raw bundle；Parquet 用于窗口特征。
- Pydantic 模型为后端事实源，并生成 JSON Schema 与前端 TypeScript 类型，禁止三套手写结构漂移。

## 2. `NormalizedCsiFrame`

正式 schema：`schemas/csi_frame.schema.json`。关键字段：

- 身份：`session_id`、`source_mode`、`link_id`、`rx_id`、`tx_id_hash`。
- 顺序：`seq`、`device_ts_us`、`host_ts_ns`。
- PHY：`channel`、`bandwidth_mhz`、`rssi_dbm`、`noise_floor_dbm`、`rate`、`secondary_channel`、`ltf_mode`。
- CSI：`csi_iq`，顺序必须保持 ESP-IDF 的 imaginary、real int8。
- 质量：解析状态、sequence gap、时间单调、备注。

正式实时传输可使用与 schema 等价的二进制编码；测试和导出必须能转成 canonical JSON。

## 3. `FeatureWindow`

```json
{
  "schema_version": "1.0.0",
  "session_id": "session-...",
  "window_id": "window-...",
  "source_mode": "live",
  "start_ns": 0,
  "end_ns": 0,
  "stride_ms": 250,
  "topology_hash": "sha256:...",
  "calibration_profile_id": "demo_room_v1",
  "links": {
    "rx-a": {
      "packet_coverage": 0.98,
      "subcarrier_coverage": 0.82,
      "amplitude_median": [],
      "amplitude_mad": [],
      "temporal_diff_rms": 0.0,
      "spectral_band_energy": {},
      "shape_correlation_to_baseline": 1.0,
      "quality_flags": []
    }
  },
  "paired_packet_coverage": 0.95,
  "feature_version": "features-v1"
}
```

窗口建议 2 秒、步长 250–500 ms。数组不进入 Agent 输入；Agent 只收到压缩摘要和可解析 evidence refs。

## 4. `SignalTriplet`

正式 schema：`schemas/signal_triplet.schema.json`。

- motion：0–1、状态、confidence。
- occupancy：low/medium/high/unknown 概率、状态、confidence。
- depth：near/mid/far/unknown 概率、状态、confidence。
- 总体：`sensor_confidence_cap`、`evidence_refs`、`status`。

所有分布总和应为 1±1e-6；`confidence` 不得大于对应信号质量；无效状态时 unknown 概率必须为 1。

## 5. `EvidencePacket`

每轮 Agent 只读取一个封存对象：

```python
class EvidencePacket(BaseModel):
    schema_version: Literal["wifi-evidence.v1"]
    session_id: str
    cycle_id: str
    sequence: int
    captured_at: datetime
    source_manifest: SourceManifest
    window_summary: WindowSummary
    topology: TopologySummary
    calibration: CalibrationSummary
    quality: QualitySummary
    signals: SignalTriplet
    evidence_index: dict[str, EvidenceValue]
    raw_ref: str
    evidence_hash: str
```

引用格式固定：

```text
evidence://{evidence_hash}/signals/motion
evidence://{evidence_hash}/quality/packet_coverage
evidence://{evidence_hash}/features/rx-a/temporal_diff_rms
```

封存后任何字段变化都会改变 hash。Agent 返回的不存在引用由 PolicyArbiter 拒绝。

## 6. `AgentClaim`

```python
class AgentClaim(BaseModel):
    claim_id: str
    cycle_id: str
    agent_id: str
    agent_version: str
    role: str
    kind: Literal["observation", "hypothesis", "alternative", "limitation"]
    state: Literal["proposed", "challenged", "revised", "conceded", "withdrawn", "accepted"]
    proposition: str
    stance: Literal["supports", "contradicts", "neutral"]
    evidence_refs: list[str]
    counter_evidence_refs: list[str]
    assumptions: list[str]
    alternative_explanations: list[str]
    falsification_test: str
    reasoning_summary: str
```

Agent 输出禁止包含 `sensor_confidence`、`physical_confidence` 或自行定义的概率字段。

## 7. `AgentChallenge`

```python
class AgentChallenge(BaseModel):
    challenge_id: str
    target_claim_id: str
    challenger_agent_id: str
    category: Literal[
        "confound", "missing_evidence", "calibration_mismatch",
        "causal_overreach", "contradiction", "stale_evidence"
    ]
    proposed_severity: Literal["info", "material", "blocking"]
    statement: str
    evidence_refs: list[str]
    resolution_test: str
    status: Literal["open", "resolved", "accepted", "rejected_by_policy"]
```

最终 severity 由确定性规则确认，不直接相信 Agent 自报。

## 8. `CouncilResult`

```python
class CouncilResult(BaseModel):
    cycle_id: str
    evidence_hash: str
    status: Literal["supported", "ambiguous", "unavailable"]
    headline: str
    summary: str
    accepted_claim_ids: list[str]
    unresolved_challenge_ids: list[str]
    alternatives: list[str]
    limitations: list[str]
    sensor_confidence_cap: float
    model_support: float
    display_confidence: float
    interpretation_agreement: AgreementSummary
    visual_parameters: dict[str, float | str]
    audio_parameters: dict[str, float | str]
    provenance: Provenance
```

强制不变量：

```text
0 <= display_confidence <= model_support <= sensor_confidence_cap <= 1
```

`interpretation_agreement` 不能进入这一公式。

## 9. WebSocket envelope

```json
{
  "schema_version": "ws-event.v1",
  "session_id": "session-...",
  "sequence": 42,
  "emitted_at": "2026-08-06T12:00:00Z",
  "event_type": "signal.frame",
  "payload": {}
}
```

客户端只应用 sequence 更大的事件。重连提交 `last_sequence`；服务器补发保留范围内的事件，否则先发完整 snapshot。

## 10. Replay manifest

必须包含：recording ID、创建时间、source mode、固件/代码/特征/估计器版本、板卡 hash、topology hash、calibration profile、信道/带宽、文件列表、checksum、ground truth 是否存在、隐私声明。校验失败则整个 bundle 拒绝加载。

## 11. 版本迁移

- patch：新增可选字段或修正说明；旧 reader 仍可处理。
- minor：新增必需行为但提供显式迁移器。
- major：不兼容；Replay 必须先转换到新 bundle，禁止静默解释。
- 每次模型、特征、标定或 prompt 更新都在 provenance 中记录独立版本。

