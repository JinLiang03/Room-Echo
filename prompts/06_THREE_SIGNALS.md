# Phase 06：三个代理信号、质量门与 EvidencePacket

## Role

你负责实现本产品最关键的确定性输出。三个信号必须来自版本化 feature + calibration，支持 unknown，并能说明何时不可信。

## Read first

`docs/PRODUCT_SPEC.md`、`docs/HARDWARE_AND_CALIBRATION.md`、`docs/DATA_CONTRACTS.md`、`docs/ACCEPTANCE_TESTS.md`、Phase 04/05 实现与报告。

## Goal

实现 `motion_intensity`、`occupancy_density_proxy`、`depth_zone_proxy`、独立质量、sensor confidence cap、事件触发和封存 EvidencePacket。

## Algorithms

### Motion

1. 对每链路标准化幅度去除帧内公共模态。
2. 计算时间一阶差分和 0.5 s 鲁棒 RMS；融合 valid carriers。
3. 以 profile 的 empty P99 映射 0、standard-walk P95 映射 1，clip 0–1。
4. 使用约 250 ms 因果 EMA；状态阈值来自 profile/config 并版本化。
5. 双链路用质量加权的保守融合；一条 invalid 时明确 single-link degraded。

### Occupancy / obstruction coverage proxy

1. 使用 2–3 s 低频偏差、异常 carrier 占比、baseline shape decorrelation 和双链路覆盖。
2. 先移除/冻结高频 motion component；若 fast motion 超出训练支持，降低 quality 或 unknown，不能把 motion 当 density。
3. 用 profile 的 ordinal/isotonic mapping 输出 low/medium/high/unknown 概率。
4. 没有匹配 profile 或依赖双链路而只剩一个 RX 时 unavailable/degraded，按训练能力决定，不能猜。

### Depth zone proxy

1. 每链路生成基线 disturbance score `qA/qB`。
2. 计算 `z=(qA-qB)/(qA+qB+eps)` 和有限的 shape asymmetry features。
3. 使用 5 点 calibration 的单调 mapping/zone boundaries，输出 near/mid/far/unknown 概率。
4. 使用约 0.8 s 因果平滑。
5. 少于两个有效非共线 RX、topology mismatch、paired coverage 不足或轴外/OOD 时 unknown。

## Quality and confidence

实现信号级质量组件：packet coverage、paired coverage、carrier coverage、clock/order、calibration match、interference、OOD、staleness。使用保守 min/明确权重方案，并在 ADR 解释。

必须满足：

```text
signal_confidence <= signal_quality
sensor_confidence_cap <= min(required_signal_quality)
unknown/unavailable => confidence = 0
```

不得把 Agent agreement 放入任何公式。

## Evidence sealing

- 每 250–500 ms 产生 SignalTriplet/quality Web 事件。
- Agent 触发条件：至少 3 s cooldown，或候选状态连续 3 个窗口改变，或重大 quality transition。
- 构建 compact EvidencePacket；数组只通过 evidence index 摘要引用。
- canonical JSON 排序、hash、只读对象；写入 audit event。
- 相同内容相同 hash；timestamp/sequence 的含义明确。

## Deliverables

- 三个 estimator 类、QualityGate、EvidenceBuilder、event trigger。
- baseline output，LLM 不存在也可完整运行。
- CLI `inspect-signals` 与 QA 图表。
- estimator/version/config manifests。
- 模型卡：训练场景、输入、输出、限制、未知条件、评估。

## Tests

- idle/walk/static obstruction/near-to-far/interference/dropout fixtures 的预期状态与单调关系。
- 单 RX depth 永远 unknown；profile mismatch occupancy/depth 不可用。
- 40% loss 两个窗口内 degraded/unavailable。
- stale 后清空上次有效状态，不残留。
- probability/invariant property tests。
- 相同 raw/profile/version → 相同 SignalTriplet/Evidence hash。
- Agent 数量字段不存在于 estimator 依赖图和 confidence 计算。

## Acceptance gate

```bash
make test-signals
make replay-signals REPLAY=data/fixtures/walk_through RECOMPUTE=1
python scripts/inspect_signals.py --replay data/fixtures/walk_through --report artifacts/signal_qa.html
```

模拟数据只验证逻辑和单调性，不允许报告真实准确率。

## Completion

通过后记录 estimator version、fixture hash、未知/降级测试；勾选 Phase 06。停止，不实现 Agent。

