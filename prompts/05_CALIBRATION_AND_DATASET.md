# Phase 05：标定、标签与数据集版本

## Role

你负责把“房间依赖”变成显式、可重复、不会数据泄漏的 calibration workflow。此阶段不追求跨房间泛化；目标是在一个固定演示空间内得到诚实的同域模型和留出评估。

## Read first

`docs/HARDWARE_AND_CALIBRATION.md`、`docs/DATA_CONTRACTS.md`、`docs/ACCEPTANCE_TESTS.md`、Phase 04 feature 实现。

## Goal

实现 calibration session、场景标签、profile fitting、trial-level split、版本/checksum、失效检测和无硬件模拟流程。

## Deliverables

1. `CalibrationProfile`：room ID、topology hash、board/antenna hash、positions、channel/bandwidth、firmware/feature/estimator version、time、environment、fit parameters、training trial IDs、metrics、expiry rules、checksum。
2. Calibration state machine：warmup → empty baseline → standard motion → occupancy levels → five depth points → held-out trials → review → active/failed。
3. CLI/API：create、record step、annotate、fit、evaluate、activate、invalidate、list、export。
4. 每个 trial 独立 raw bundle；label 只存 `ground_truth.json`，不混入 raw/events 给 Agent。
5. Trial-level train/validation/test split；禁止把同一连续录制切帧后分散到不同集合。
6. 空场 median/MAD、stable carriers、motion scale、occupancy ordinal mapping、depth monotonic/zone mapping。
7. Profile 与 source manifest/topology 的 match score 和 hard invalidation。
8. `scripts/calibration_wizard.py`：文字指导、倒计时、质量预检、重录、进度和最终报告。
9. Mock calibration：从确定性 scenario 生成 profile，用于 CI；明确 `simulated=true`，不能当硬件报告。
10. `calibration_report.json/html`：trial、split、曲线、metrics、失败项、版本和限制。

## Data discipline

- labels：empty/low/medium/high 是场景扰动等级，不等于人数。
- depth：5 个位置是沿预设 axis 的 ordinal point，不输出米制预测。
- 所有重复轮次随机顺序，避免时间/温漂与标签完全相关。
- fit 时不读取 held-out test；调参只用 train/validation；最终 test 一次性报告。
- 每次更换 feature/estimator version 必须重新评估 profile。
- 不覆盖旧 profile；新版本并存并有 active pointer。

## Baseline models

- Motion：空场 P99 → 0，标准行走 P95 → 1 的鲁棒标度。
- Occupancy：低频 anomaly ratio + shape decorrelation 的 isotonic/ordinal baseline；必须输出概率/unknown。
- Depth：双链路 disturbance asymmetry 的单调 mapping 或小型可解释 classifier；必须接受 single RX unknown。

避免神经网络。只有 baseline 在真实留出集仍明显不足且数据量足够时，才提交独立 ADR 和消融计划，不在本阶段直接引入。

## Tests

- topology/channel/firmware/feature 变化导致 hard invalidation。
- trial split 无 ID/时间重叠；ground truth 不出现在 feature/Agent 输入。
- 同一输入拟合 profile 可复现。
- profile checksum/签名错误被拒绝。
- 不完整步骤、低 packet coverage、carrier 不足时 wizard 要求重录。
- Mock profile 的 simulated 标记无法被改成 live report。

## Acceptance gate

```bash
make test-calibration
python scripts/calibration_wizard.py --mode mock --scenario demo_room_v1
python scripts/evaluate_calibration.py --profile data/calibration/demo_room_v1
```

检查报告、split 和 ground-truth isolation。没有硬件时只验证 simulated workflow；Live metrics 留到 Phase 11。

## Completion

通过后记录 profile schema/version 和模拟报告；勾选 Phase 05。不要把模拟 metrics 当真机结果。

