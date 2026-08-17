# Phase 03：Collector、Raw 录制、Mock 与 Replay

## Role

你负责建立可靠的输入边界。目标是让真实串口、固定录制和确定性模拟对上层完全等价，并保证 raw 数据可复现、可校验、不可被下游修改。

## Read first

`docs/ARCHITECTURE.md`、`docs/DATA_CONTRACTS.md`、`docs/ACCEPTANCE_TESTS.md`、`docs/WIRE_PROTOCOL.md`。

## Goal

实现 `FrameSource`、串口 parser、双 RX 配对、append-only raw writer、Replay bundle、Mock 场景与录制 CLI。此阶段只输出合法 frames/health，不做正式信号估计。

## Deliverables

1. `MockFrameSource`：固定 seed 生成 idle、walk-through、static-obstruction、interference、rx-dropout、packet-loss 场景。
2. `ReplayFrameSource`：虚拟时钟、pause/resume/seek、0.25×–4×、step、recompute flag。
3. `SerialLiveFrameSource`：两个独立串口任务、自动重连、明确端口配置；绝不猜设备。
4. 增量 binary parser：处理任意 chunk 边界、noise、CRC、未知版本和 resync。
5. 双链路 pairing：按 TX seq；保留 unmatched、late、duplicate、wrap counters；设置有界等待。
6. Raw writer：先写临时 bundle，fsync/close 后原子发布 manifest 与 checksum；中断恢复/标记 incomplete。
7. Replay verifier：checksum、manifest、schema、版本、文件存在、禁止路径穿越。
8. 数据去标识：真实 MAC 使用 per-session salt hash；export 不含串口绝对路径。
9. CLI/API：list ports、start record、stop、verify bundle、replay、inspect manifest。
10. 至少一个由 mock 生成但按 live wire protocol 录制的 frozen fixture。

## Replay bundle

严格实现 `manifest.json`、`raw.csi.zst`、`events.jsonl`、`checksums.sha256`；features 与 ground_truth 可在后续添加。ground truth 独立文件且 source interface 默认不读取。

## Failure behavior

- 一个 RX 断开：source health degraded；继续发单链路 frame；不伪造另一链路。
- TX seq gap：记录质量，不补帧。
- 磁盘写失败：Session error 并停止，不能输出看似完整的 bundle。
- Replay checksum 错：整体拒绝。
- 串口 reconnect：新 epoch/事件，避免 seq 误配。
- Web 客户端断线：不影响 raw 录制。

## Tests

- parser property/fuzz test：随机分块、噪声、截断、CRC、重复。
- 10 分钟 synthetic stream 无内存无界增长。
- live-style fixture → record → replay，NormalizedCsiFrame 序列等价。
- 相同 seed 两次 mock bundle checksum 一致，除明确排除的创建时间字段。
- 40% packet loss、掉单 RX、seq wrap、serial reconnect 结果正确。
- 恶意 manifest/路径穿越/zip bomb 风格输入被拒绝。

## Acceptance gate

```bash
make test-collector
make generate-fixtures
make verify-replay REPLAY=data/fixtures/walk_through
make replay-smoke REPLAY=data/fixtures/walk_through
```

记录解析吞吐、队列上限、fixture checksum 和 round-trip 结果。没有硬件不影响通过；Live 只标为未真机验证。

## Completion

通过后更新状态，勾选 Phase 03。停止，不实现特征或三信号。

