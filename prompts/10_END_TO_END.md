# Phase 10：全链路集成、故障注入与两分钟 Demo

## Role

你负责把已验证模块组合成真正一键运行的本地产品。此阶段以 Replay 全链路为发布基线，Live 使用同一接口但不伪造硬件通过。

## Read first

所有 canonical docs、所有已完成 Phase 的 State/ADR、`docs/ACCEPTANCE_TESTS.md`。

## Goal

让 mock/replay/live 使用统一 session lifecycle；完成 API、WS、Demo scenario、故障注入、观测、E2E 和初版 release report。

## Deliverables

1. 一键命令：

```bash
make dev MODE=replay
make demo MODE=replay SCENARIO=walk_through
make demo MODE=mock SCENARIO=interference
make dev MODE=live RX_PORTS=...
make test
```

2. Session API 全部状态与幂等/错误响应；切换 mode 必须新 Session。
3. WebSocket event log、sequence、heartbeat、snapshot/reconnect、backpressure。
4. `walk_through` 2 分钟 frozen raw fixture：idle → far entry → approach → occupancy change → ambiguous interference → recovery。
5. Mock Council 在该 fixture 中产生主张、material challenge、修订/让步、Policy rejection 和 Fusion result。
6. Fault injector：packet loss、single RX、TX stale、profile mismatch、LLM timeout/invalid JSON、disk error、WS disconnect/out-of-order。
7. Observability：结构化日志、queue depth、packet/window/agent latency、errors、version/provenance；无 secrets/raw MAC。
8. `scripts/run_demo.py`：预检、启动、浏览器 URL、场景进度、停止和 artifact 路径。
9. `scripts/verify_release.py`：执行非硬件 Gate，生成 `release_report.json`。
10. 完整 operator README：首次安装、Replay demo、Live 准备、常见故障、数据位置、隐私。

## E2E cases

- Happy Replay：raw→features→signals→evidence→debate→policy→multimodal。
- Agent offline：三信号/visual 继续，Council unavailable。
- 40% loss：两个窗口内 degraded/unknown。
- Single RX：depth unknown；其他允许信号继续。
- Profile mismatch：occupancy/depth unavailable。
- Old Agent result：不能覆盖新 cycle。
- WS reconnect：无重复/倒序 UI 状态。
- Replay corruption：启动前拒绝。
- Stop/Restart：资源释放、Session/new sequence 正确。

## Performance

- 记录 signal→WS→UI p50/p95/p99。
- 运行至少 60 分钟 Replay soak；队列有界、无 crash；内存增长目标 <10%。
- LLM 路径可以 opt-in，mock 路径必须稳定；Agent 15 s deadline。
- 浏览器页面目标 60 FPS；不把数据插值帧算为传感率。

## Demo script verification

按 `WEB_UX_SPEC.md` 的时间顺序跑完 2 分钟；录制关键截图/视频片段或 Playwright trace。观众第一屏能看到：当前 mode、数据 freshness、三信号、质量、限制、水印。争论页能看见证据引用和真实分歧。

## Acceptance gate

```bash
make test
make e2e-replay
make fault-injection
make soak-replay DURATION=60m
python scripts/verify_release.py --mode replay --output artifacts/release_report.json
```

所有 Replay Gate 必须通过；Live 项目在 report 中是 `not_run` 或 `blocked_by_hardware`，不能 passed。

## Completion

通过后勾选 Phase 10；在 State 写一键命令、报告、截图、性能和 Live 未验证项。停止，不自动进入硬件 flash。

