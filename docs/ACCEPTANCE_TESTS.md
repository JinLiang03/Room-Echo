# 验收测试

这些是目标门槛，不是预先承诺。若未达到，项目必须记录失败并降级，不能降低阈值、删除测试或用 Agent 文本掩盖。

## 1. Schema 与确定性

- 所有示例对象通过 JSON Schema/Pydantic 校验。
- 概率分布总和为 1±1e-6；unknown 状态的 unknown 概率为 1。
- 同一 raw bundle、版本、profile、seed 重复运行，确定性 feature/signal 输出字节级一致或通过记录的浮点容差。
- Live 录制再以 Replay `recompute=true` 运行，feature/signal/quality 等价。
- ground truth 不出现在 EvidencePacket、Agent prompt 或 trace input。
- checksum 错误、文件缺失或 schema major 不兼容时拒绝整个 Replay。

## 2. 置信与 Agent 安全

1. 同一 EvidencePacket 分别启用 1/3/6 个 Agent，`display_confidence` 完全相同。
2. 全部 Agent 同意时，结果仍不超过 `sensor_confidence_cap`。
3. 重复同一证据十次不提高结果。
4. 未解决 challenge 只能保持或降低可显示状态。
5. 单 RX 时 depth 为 unknown。
6. topology/calibration 不匹配时 occupancy/depth unavailable。
7. unavailable 不得被 Fusion 用语言补全。
8. 非法 JSON、虚构证据、过期 hash 和越权结论均被 Policy 拒绝。
9. 每个最终主张可追溯到同一 evidence hash。
10. Agent 超时/全离线时信号 UI 和 baseline 仍持续。

## 3. Replay / Backend 性能

| 测试 | 通过条件 |
| --- | --- |
| Signal → Web | p95 <300 ms，目标机、1× Replay |
| Web rendering | 1440×900 与 390×844 无溢出/遮挡；视觉目标 60 FPS |
| Agent cycle | p50 <8 s；15 s 硬降级，不积压多轮 |
| 60 min soak | 无崩溃、队列有界、进程内存增长 <10% 目标 |
| WebSocket reconnect | 按 sequence 恢复，无旧周期覆盖新结果 |
| Backpressure | UI 可丢中间视觉帧；raw 录制不丢且失败会停止 Session |

## 4. 真机采集

| 测试 | 目标门槛 |
| --- | --- |
| 30 min 稳定性 | 每 RX 平均 ≥95 包/s；99% 的 1 s 窗口 ≥90 包；总丢包 <5%；无重启、无持续可用内存下降 |
| 双链路配对 | 每秒 ≥90 个相同 TX seq 同时出现在两个 RX |
| 空场误报 | 20 min 中 motion <0.15 的时间 ≥95%；motion >0.5 且持续 300 ms 的误报 ≤1 次/10 min |
| 运动检测 | 20 次标准路径召回 ≥95%；首次响应 ≤500 ms；停止后 2 s 内回落 |
| 占用代理 | 留出轮次 Spearman ρ ≥0.75；归一化 MAE ≤0.20 |
| 纵深代理 | 5 点单调排序正确 ≥85%；归一化中位绝对误差 ≤0.15；方向判断 ≥90% |
| 次日复测 | 设备不移动、快速空场重标定后，以上指标下降 ≤20% |
| 干扰/OOD | 开关门、移动椅子、拥塞等能进入 degraded/invalid，不继续高置信输出 |

如果 occupancy 未通过，只能改名并显示为“信道扰动覆盖度”；如果 depth 未通过，正式 UI 设为 unknown 或实验模式，不得保留近/中/远的强主张。

## 5. 故障注入

- 注入 40% 丢包：两个窗口内 degraded/unavailable。
- 拔掉一个 RX：motion 继续；depth 关闭；依赖双链路的 occupancy 降级或关闭。
- 停止 TX：两个窗口内 stale，停止推断并清除当前态残影。
- 改 topology hash：拒绝旧 profile。
- 注入时间回退/重复 seq：帧隔离并计数，不污染窗口。
- 模拟磁盘写满：停止 Session，raw 不假装完整。
- 模拟 Agent 非法 JSON/虚构引用/“墙后有人”：Policy 拒绝并写审计事件。
- 新证据到达时旧 Agent 结束：旧结果不覆盖新 snapshot。
- WebSocket 断开再连接：最后 sequence 后补发或发送全量 snapshot。

## 6. Web 与多模态

- 首屏无需操作即可看到状态、三项数据、数据新鲜度和限制。
- 明确区分 measurement quality、model support、interpretation agreement。
- 所有曲线、卡片、snapshot 和导出值一致。
- 抽象视觉始终带“非真实影像”水印；无人体轮廓/真实热图。
- 声音默认静音，可完整关闭；减少动态可用。
- unknown 不使用危险色，不残留上次有效视觉。
- 数据更新率与渲染帧率分开显示。
- Council 只展示短依据和 evidence chips，不展示隐藏思维链。

## 7. 发布门

最终 `release_report.json` 必须列出每个 Gate 的 `passed | failed | not_run | blocked_by_hardware`、命令、版本、时间和 artifact 路径。只有所有 Replay gate 通过、Live gate 有真实证据、产品 claim 与结果一致时才标记 release candidate。`blocked_by_hardware` 不能算 passed。

