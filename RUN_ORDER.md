# 使用顺序

## 推荐方式：逐阶段交给 Codex

每次只复制一份 `prompts/NN_*.md` 的完整内容给 Codex。Codex 必须读根目录的 `AGENTS.md`、`PROJECT_INDEX.yaml`、`STATE.md`、`TASKS.md` 和提示词中指定的文档，然后实施、运行验证、更新状态。

| 阶段 | 目标 | 可在无硬件时执行 |
| --- | --- | --- |
| 01 | 工程骨架、契约和本地启动 | 是 |
| 02 | ESP-IDF TX/RX 固件 | 可编译，不能真机验收 |
| 03 | 串口采集、录制、Mock、Replay | 是 |
| 04 | CSI 清洗与特征管线 | 是 |
| 05 | 标定、标签和数据集版本 | 部分；现场采集后完成 |
| 06 | 三个数据和置信度门控 | 是，先用 fixture |
| 07 | 多 Agent 争论与离线回退 | 是；真模型需 API key |
| 08 | Web 实时体验 | 是 |
| 09 | 动态推断场、音景和结果卡 | 是 |
| 10 | 全链路、故障注入、演示脚本 | 是 |
| 11 | 三板真机与现场指标 | 否 |
| 12 | 稳定性、发布和交接 | Replay 可先做，最终需真机 |

## 一次性方式

把 `prompts/00_MASTER_BUILD.md` 给 Codex。它会逐阶段执行，但仍必须在每个 Gate 停下来验证。若硬件不存在，第 11 阶段应标记为 `blocked_by_hardware`，而不是伪造完成。

## 每阶段统一启动句

```text
执行本提示词对应阶段。开始前读取 AGENTS.md、PROJECT_INDEX.yaml、STATE.md、TASKS.md 以及提示词列出的规范。先检查当前仓库，再实现；运行所有本阶段验收；只在真实通过后更新 STATE.md 和 TASKS.md。不要执行下一阶段。
```

## 运行形态

最终应提供一条开发命令和一条演示命令，建议形态如下，实际由 Phase 01 固化：

```bash
make dev MODE=replay
make demo MODE=replay SCENARIO=walk_through
make dev MODE=live RX_PORTS=/dev/ttyUSB0,/dev/ttyUSB1
make test
make test-hardware
```

## 发生失败时

1. 保留失败日志和原始数据。
2. 在 `STATE.md` 写明失败门、复现命令、影响范围和下一步。
3. 不要调低验收阈值或删除测试。
4. 若房间、设备或标定条件改变，创建新的 calibration profile，不能覆盖旧结果。

