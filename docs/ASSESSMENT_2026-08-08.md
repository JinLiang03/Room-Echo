# 源码、前端与 Demo 就绪度评估

评估日期：2026-08-08。对象：Phase 12 `phase12/demo-hardening` 工作树。

## 结论先行

当前可以作为 **Replay demo candidate**，但还不能称为 **Final Live demo**。
Replay 的数据链、恢复、控制、性能、离线降级、置信边界和发布包都通过了
自动门。Live 仍缺三块板、实地拓扑、非模拟标定、30 分钟稳定性与
held-out 测量，因此持续 fail closed。

## 前端与硬件同事如何并行

不建议再复制一套独立前端。两套 UI 会很快出现合约、按钮语义和现场
修复不同步。建议保持一个 Web 应用、三条工作线：

| 工作线 | 职责 | 可合并条件 |
| --- | --- | --- |
| `feat/frontend-v2` | Home / Observe / Why / Replay 交互与视觉 | Mock + Replay 绿，桌面/移动截图已审 |
| `hardware/live-validation` | 串口角色、烧录、房间拓扑、标定与 Live 证据 | 三个明确设备 + 非模拟 profile + 硬件报告 |
| `phase12/demo-hardening` | 统一集成、合约、发布门和候选版 | `make release-check` 0 失败，manifest 按模式 fail closed |

同步靠的不是手工拷贝，而是四个稳定边界：Pydantic → JSON Schema →
TypeScript 合约；Live / Replay / Mock 共用 `FrameSource`；WS event envelope；
Replay manifest + profile/topology/firmware hash。前端只靠这些边界开发，就不必
等硬件；硬件数据回来后，应该只替换 source 和证据，不替换 UI。

## 前端产品上限与最优交互

上限是一台“可解释、可回放、可降级的空间信号仪器”，不是相机替代品。
视觉质量再高，也不应越过三条线：不呈现真实影像，不声称人数/身份/
姿态，不把相对纵深变成米制距离。

最优演示路径是：

1. **Ready**：先说明 Live / Replay、RX 拓扑、profile 和就绪度。
2. **Observe**：首屏只放三个代理信号、抽象推断场和一句受限结论。
3. **Why**：点击结论后展开 Evidence、Agent 分歧、让步和 Policy 拒绝。
4. **Replay**：回到关键时刻，用同一 evidence hash 复现结论。

当前 Home 已把数字家具形态明确标为手选视觉主题，不是检测到的物体；
Observe/Council/Evidence/Replay 继续承担审计。下一个 UX 优先项是移动端
渐进披露，而不是再增加一屏并列卡片。

## 静态测评

| 范围 | 结果 | 解读 |
| --- | --- | --- |
| Python lint / types | ruff 通过；mypy 65 个源文件通过 | 无静态错误 |
| 合约漂移 | 43/43 | Schema、TS、fixture 一致 |
| Python 回归 | 264 通过，1 个 opt-in OpenAI 测试跳过 | 默认 Mock/Replay 不依赖外部 LLM |
| Web | 58/58；typecheck/build 通过 | Lint 0 error / 5 条 Fast Refresh warning |
| Claim audit | 11677 行，0 findings | 代理/未知/非影像表述通过 |
| 依赖/安全 | 84 Python + 19 Web；运行时 copyleft 0；secret 0 | `esptool` 仅独立工具待人工备核 |
| 公开发布 | 未就绪 | 项目自身尚无 LICENSE；私有仓库不受此阻断 |

## 动态测评

| 场景 | 结果 |
| --- | --- |
| Replay 服务链 | 2/2，完整 raw → features → signals → evidence → council → result |
| 真实全栈 Playwright | 10/10，桌面 + 移动；含刷新/晚加入、反向 seek、paused step |
| 离线 UI Playwright | 38 通过，2 个冗余截图用例跳过 |
| 多模态性能 | 60 FPS，156 draw calls，1 dropped frame，303 事件，通过 |
| 故障注入 | 8/8 |
| 60 分钟 Soak | 3638 s，85 轮，0 crash，queue 400/400 有界，RSS +2.37%，p95 最大 29.572 ms |
| 发布门 | 13 passed / 0 failed / 1 not_run / 2 blocked_by_hardware |

本轮还通过动态测评抓到并修复了：replay 不能真回绕、step 语义不稳定、
刷新后丢 Council/source health、latency 时钟域错误、Sparkline NaN、Canvas 性能统计
失真、Story 误报断线，以及清洗器的逐载波 median CPU 热点。清洗语义未改变，
30 秒双链路基准已回到 15 秒门内，完整服务 Replay 降至约 20 秒。

## 与 MiroFish 及最初架构的差距

详细对齐见 [`ARCHITECTURE_ALIGNMENT.md`](ARCHITECTURE_ALIGNMENT.md)。要点是：

- MiroFish 是文档 → 知识图谱 → Agent 社会模拟 → 报告的长任务；本项目是
  CSI → 因果清洗 → 标定代理信号 → 受限 Council 的实时系统。
- 可借鉴的是 MiroFish 的分阶段 workflow、进度可视化和完成后追问；不应引入
  Zep/OASIS 或复制 AGPL 代码来替换传感链。
- 最初架构的 CSI、清洗/基线、三信号、Agent 争论、视觉/声音/文字已有实现。
- 仍缺：真实硬件证据；可查询的 Session/Evidence 索引（当前不是数据库）；
  灯光/机械安全适配器；移动端渐进披露。

## GitHub 同步建议

现在就应同步，但应创建 **private repository**，并且只推送绿色检查点，
不是每次保存就 push。建议节奏：功能分支小提交 → PR 跑 Replay 门 →
集成分支产生 manifest/tag → 硬件同事只拉取该 tag。禁止上传 `data/raw/`、
`.env*`、串口记录、房间几何和未脱敏报告。对外 public 前必须先确定项目
LICENSE，并再做一次依赖许可评审。
