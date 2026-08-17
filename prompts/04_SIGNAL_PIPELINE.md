# Phase 04：确定性 CSI 清洗、窗口与特征

## Role

你是无线感知信号工程师。建立可解释、可版本化、可离线复算的 baseline 管线；优先鲁棒统计而不是未经同域验证的深度模型。

## Read first

`docs/HARDWARE_AND_CALIBRATION.md`、`docs/DATA_CONTRACTS.md`、`docs/OPEN_SOURCE_AUDIT.md`、Phase 03 source/fixtures。

## Goal

把 NormalizedCsiFrame 转为经过质量检查的 FeatureWindow。此阶段不输出最终三项分类，也不调用 LLM。

## Pipeline

1. 验证 link、PHY、channel、bandwidth、CSI length 与 session manifest 一致。
2. 处理 `first_word_invalid`；统一 LTF 和 subcarrier map；屏蔽 DC/guard/不可用 carrier。
3. IQ → complex → amplitude dB；phase 仅做单 RX 内可验证处理，不跨 RX 比较绝对相位。
4. 检测增益/全子载波公共模态；用鲁棒中心化或官方示例可验证方法补偿。
5. 空场 median/MAD 标准化；剔除空场最不稳定 20% carrier，剩余 <32 则 link invalid。
6. Hampel/鲁棒异常点策略和轻量低通；所有参数写入 feature version/config。
7. 2 s 窗口、250–500 ms stride；不能用未来帧污染在线输出。
8. 单链路特征：temporal diff RMS、robust variance、amplitude anomaly ratio、baseline shape correlation、频带能量、spectral entropy、valid carrier ratio。
9. 双链路特征：paired coverage、两个 link disturbance score、amplitude-shape asymmetry；不使用跨设备原始 phase。
10. 质量：packet coverage、paired coverage、timestamp monotonic、calibration match、interference/OOD 基础分数和 flags。

## Deliverables

- 纯函数/可组合 transformer；fit 与 transform 分离。
- `FeatureConfig`、`FeatureVersion`、subcarrier map 单元测试。
- `FeatureWindow` Parquet writer/reader 与 schema version。
- `scripts/extract_features.py`，支持 bundle、区间、profile、recompute、output。
- 诊断图生成：carrier stability、packet rate、baseline distribution、feature timelines；用于研发，不进入正式视觉。
- baseline benchmark 和 ADR：为什么 MVP 不用跨 RX phase/AoA/ToF。

## Open-source comparison

可在 `research/adapters` 中使用 CSIKit/csiread 对 frozen fixture 解析做对照。可重写并消融 ESPectre 的算法思想，但不得复制 GPL 代码进非 GPL 主模块。每个对照记录 commit、license、input adapter 和差异。

## Tests

- 合成 IQ 的 amplitude、carrier index 和 invalid-word 处理有 golden truth。
- 滤波器在线实现不偷看未来。
- 不同 chunk/window 切分产生一致结果。
- 空场噪声、步行扰动、共同增益变化、单 carrier spike、40% 丢包场景有预期质量/特征。
- single RX 不生成伪 paired feature。
- raw bundle → features 两次运行可复现。
- 性能足以持续处理 2×100 packet/s，CPU/内存基线记录。

## Acceptance gate

```bash
make test-sensing-core
python scripts/extract_features.py --replay data/fixtures/walk_through --recompute
make benchmark-sensing
```

输出特征 QA 报告与版本。不得根据 ground truth 调参到 fixture；参数调整需在 calibration 阶段完成。

## Completion

通过后更新 State/Tasks，记录 fixture hash、feature version、性能。停止，不实现 Phase 05/06。

