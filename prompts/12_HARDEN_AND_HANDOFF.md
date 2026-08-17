# Phase 12：稳定性、安全、发布与交接

## Role

你是发布负责人。收敛依赖、性能、故障、隐私、文档和可重复启动，确保别人拿到项目能理解它能做什么、不能做什么、如何验证。

## Read first

所有 State、reports、ADRs、canonical docs、当前 diff 与依赖清单。

## Goal

修复剩余的 P0/P1 问题，完成 soak、安全/许可证审计、release report、用户/开发/现场文档和可复现包。不要增加新功能。

## Work

1. 汇总所有 failed/not_run/blocked Gate，先修 P0：crash、数据损坏、置信越界、stale 残影、secret 泄露、错误 claim。
2. 完整测试矩阵：Python、TS、Firmware build、Replay E2E、Playwright、property/fuzz、fault injection、hardware（若可用）。
3. 60 分钟 Replay soak；30 分钟 Live soak 若 Phase 11 已具备；记录 CPU、内存、队列、丢包、latency、reconnect。
4. 依赖/许可证审计：锁文件、SBOM、A/B 项目 pinned commit；GPL/无许可证代码不得误入主包。
5. 安全：secret scan、CORS/localhost 默认、输入尺寸/路径、Replay checksum、日志脱敏、数据保留/删除。
6. Firmware：size、stack/heap、overflow counters、WDT/reboot reason、串口 backpressure、build reproducibility。
7. Web：production build、bundle size、错误态、reduced motion/audio、desktop/mobile screenshot final QA。
8. Agent：prompt/model/version provenance、cost/latency、offline fallback、Policy regression corpus。
9. 文档：README、QUICKSTART、LIVE_SETUP、CALIBRATION、DEMO_SCRIPT、TROUBLESHOOTING、PRIVACY、LIMITATIONS、ARCHITECTURE、CONTRIBUTING。
10. 生成 release artifacts 和最终 `release_report.json/html`；每项有 evidence path。

## Claim review

逐句审查 README、UI、Demo 台词和报告，删除/改写：完美成像、透视、墙后人体、人数、姿态、绝对墙密度、米制深度、通用跨房间准确率。保留准确表述：活动强度、相对遮挡/空间占用代理、已标定轴的相对纵深代理、抽象信号解释。

## Release commands

最终至少实现并验证：

```bash
make setup
make demo MODE=replay SCENARIO=walk_through
make test
make release-check
```

有硬件时另有明确 `LIVE_SETUP`，不应要求修改源码或把密码写入 repo。

## Acceptance gate

- 所有 Replay Gate passed。
- Hardware Gate 只有在真实运行后才可能 passed；否则明确 not_run/blocked。
- 无 P0；P1 有明确 owner/impact/workaround 才可发布候选。
- SBOM、license、secret、privacy checks 通过。
- 最终文档从干净环境按 quickstart 验证。
- 2 分钟 Demo 跑通，所有数值、结果、水印和 provenance 一致。
- 打包后重新展开，checksum 与 smoke test 通过。

## Completion

仅在所有适用发布门完成且 `release_report.json` 与真实证据一致后，更新 `STATE.md` 和 `TASKS.md`，创建 release candidate 标签或归档。任何 failed、not_run 或 blocked 项都必须保留在最终交接中。

## Final response

完成后只汇报：

1. 最终启动命令和 URL。
2. Replay/Live 各自真实状态。
3. 三信号的实测 Gate 结果。
4. Agent/Web/故障/soak 摘要。
5. release artifacts。
6. 未通过或未运行项及影响。

不要用“全部完美”概括；让报告说明实际完成度。
