# Phase 11：三板真机、现场标定与指标验收

## Role

你是现场硬件与实验负责人。只报告真实观察到的板卡、串口、数据和指标；不让 Mock/Replay 结果混入 Live 结论。

## Read first

`docs/HARDWARE_AND_CALIBRATION.md`、`docs/ACCEPTANCE_TESTS.md`、Firmware manifest、operator README、当前 State。

## Prerequisite gate

先只读检测并列出：

- 三块板的实际 target/revision、USB serial、端口、天线与供电；
- ESP-IDF/esp-csi pinned versions；
- 房间、预定位置、信道扫描和 5 点 depth axis；
- 当前待 flash 的确切 TX/RX build hash。

若缺三块板、端口不明确、target 与 build 不匹配或用户未准备现场，停止并标 `blocked_by_hardware`。绝不猜端口或向未知 USB 设备 flash。

## Goal

确认设备映射后，flash 1 TX + 2 RX，执行采集 QA、完整标定、留出测试、干扰/掉线/次日复测，并生成不可伪造的 hardware report。

## Procedure

1. 将每个 USB serial 显式绑定为 TX/RX-A/RX-B，保存映射并再次确认。
2. 分别 flash 对应固件；保存命令、build hash、flash result 和 boot log。
3. 运行 5 分钟 sanity：信道/带宽/TX ID、包率、CSI length、RSSI/noise、heap、overflow、reboot。
4. 固定三角拓扑和天线方向；生成 topology hash。
5. 完整执行 calibration wizard：30 s warmup、120 s empty、3× standard walk、occupancy levels、5× depth points、held-out trials。
6. 激活 profile 前检查 split、quality 和 test 未泄漏。
7. 运行 `ACCEPTANCE_TESTS.md`：30 分钟稳定、20 分钟空场、20 次运动、occupancy/depth 留出、干扰和掉板。
8. 若时间允许按协议做次日/冷启动快速重标定复测；未做就 `not_run`，不能省略说明。
9. 将完整 Session 录制为 Replay，再 `recompute=true` 对比 Live 输出。
10. 在 Web 跑 2 分钟现场 Demo，并保存截图/trace 与所有 provenance。

## Measurement discipline

- 任何调参必须只使用 train/validation trial；test 不可反复看后调整。
- 每次硬件/位置/信道变化新建 profile 与 test run。
- 不删除失败 trial；标明 protocol violation 后可排除，但理由与原始数据保留。
- 不修改验收阈值。未通过则让对应功能降级/改名/unknown。
- 结果只对该 room/topology/firmware/profile 有效，不外推跨房间。

## Required reports

- `hardware_inventory.json`
- `topology.json` + 布置照片/手工图路径（若用户同意记录）
- `firmware_flash_report.json`
- `capture_qa_report.html/json`
- `calibration_report.html/json`
- `live_acceptance_report.html/json`
- `live_vs_replay_report.json`
- raw bundles + checksums

## Acceptance gate

运行项目提供的等价命令：

```bash
make hardware-sanity RX_PORTS=... TX_PORT=...
make calibrate-live PROFILE=demo_room_v1
make test-hardware PROFILE=demo_room_v1
make compare-live-replay RECORDING=...
```

若所有目标通过，标 passed。若 occupancy/depth 未通过，按文档降级 UI，并让相关 release Gate failed；其余系统可继续作为 motion/艺术 Demo。

## Completion

更新 State/Tasks 和 release report，引用真实 artifacts。不要因为“画面看起来不错”覆盖 metric failure。停止。

