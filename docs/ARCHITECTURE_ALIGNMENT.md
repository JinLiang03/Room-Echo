# 架构对齐与 MiroFish 差距评估

评估时间：2026-08-08。当前仓库基线：Phase 12 Replay hardening；Live
硬件证据仍为 `blocked_by_hardware`。

## 结论

这个项目不应该“改造成 MiroFish”。两者的共同点是多 Agent 与可追溯过程，
但核心任务不同：

- 本项目是实时、受标定约束的 Wi-Fi CSI 代理信号系统，首要指标是数据链不断、
  置信边界诚实、结果可回放。
- MiroFish 是从文档种子构建知识图谱、生成 Agent 人设并运行社会模拟的批处理
  推演系统。官方流程是 Graph Building → Environment Setup → Simulation →
  Report → Deep Interaction。

应该借鉴 MiroFish 的“分阶段任务流、过程进度和完成后深度交互”，不应引入
Zep、OASIS 或大量 Agent 来替代当前的确定性传感链，也不应把 CSI 输出包装成
“高保真数字世界”。

## 与最初技术架构图逐项对齐

| 最初架构层 | 当前实现 | 状态 | 仍缺内容 |
| --- | --- | --- | --- |
| WiFi CSI 原始信号 | ESP32 TX + RX-A/RX-B、二进制 CRC 协议、Live/Replay/Mock `FrameSource`、append-only raw bundle | 软件完成，Live 未实测 | 三板角色确认、串口映射、烧录与现场采集报告 |
| 信号清洗与环境基线 | 因果清洗、2 秒窗口、双链路配对特征、版本化 Calibration Profile | Replay/模拟标定完成 | 同一房间的 recorded、non-simulated 标定；held-out 指标 |
| 阻隔密度 / 扰动活性 / 传播纵深 | `occupancy_density_proxy`、`motion_intensity`、`depth_zone_proxy`，含 unknown 与质量门 | 完成 | Live 条件下验证阈值；单 RX 时 depth 必须 unknown 的现场证据 |
| 空间状态数据库 | raw zstd、features parquet、事件 NDJSON、WS 有界 ring 与 snapshot/catch-up | 部分完成 | 当前不是可查询的“空间状态数据库”；若要跨 Session 比较，需要轻量 Session/Evidence 索引，而不是先上向量数据库 |
| 多个解释 Agent | architecture / biota / feng_shui / psyche / soundscape + skeptic + fusion；只读 `EvidencePacket` | 完成 | DeepSeek 已在指定公网提交上完成真实调用证明；OpenAI 仍为 opt-in，默认 Mock 只代表确定性演示 |
| Agent 协商或争论 | propose → challenge → respond → policy → synthesize；主张、来源、挑战、让步、拒绝均可审计 | 完成 | 当前是一轮受预算约束的 Council，不是长期记忆、多轮社会演化 |
| 视觉 | Canvas 2D 抽象无线电干涉场、三信号卡、证据与争论 | 完成 | 下一版需要渐进披露，尤其压缩移动端长页 |
| 声音 | Web Audio 映射、手势启用、默认静音、失焦/暂停渐隐 | 完成 | 真机扬声器与展场声学验收 |
| 文字 | 受限结论、替代解释、限制、来源与可见分析步骤 | 完成 | 将默认首屏压缩成一句结论，长过程按需展开 |
| 灯光 | 无生产输出适配器 | 未实现 | 版本化 `ActuatorCommand`、亮度/频率上限、手动急停、模拟器与设备驱动 |
| 机械运动 | 无生产输出适配器 | 未实现 | 只有在安全评审后接入；必须有行程/速度限制、互锁与失联归零 |

## 与 MiroFish 的结构差异

本次对照基于官方仓库 `666ghj/MiroFish` 的 `main`，读取时 HEAD 为
[`b5b53acc`](https://github.com/666ghj/MiroFish/commit/b5b53acc57189a4a42e44a23e149dc655c98fe82)。

| 维度 | 本项目 | MiroFish | 决策 |
| --- | --- | --- | --- |
| 实现栈 | FastAPI + React/TypeScript + Pydantic contracts + WebSocket | Flask + Vue + Zep Cloud + OASIS/CAMEL | 不替换主栈；只借鉴任务进度与信息架构 |
| 输入 | 高频 CSI → 窗口特征 → 三个标定代理 | 文档/报告 → 本体 → Zep 知识图谱 | 保持分离；不要让 LLM 接触 raw CSI |
| 运行形态 | 实时信号流，Council 不能阻塞 UI | 长任务式图谱构建和社会模拟 | 前端借鉴阶段进度，不照搬执行引擎 |
| Agent 规模 | 5 个解释者 + skeptic + fusion，固定预算 | OASIS 双平台 Agent 社会模拟与动态记忆 | 不追求 Agent 数量；本项目优先证据密度与响应时间 |
| 记忆 | EvidencePacket、事件日志、静态知识库 | Zep 图谱、实体关系、模拟状态与时序记忆更新 | 若新增数据库，只索引 Session/Evidence，不引入用户画像式长期记忆 |
| 输出 | 实时代理状态、受限解释、抽象场和声音 | 预测报告、模拟世界、单 Agent / ReportAgent 交互 | 可借鉴“报告后追问”，但回答仍必须绑定 evidence hash |
| 交互 | Observe/Council/Evidence/Replay 并列工具页 | 明确的五步 Workflow，图谱/分屏/工作台切换 | 将最终 Demo 改为 4 步主流程，专家页降为二级抽屉 |
| 恢复 | WS snapshot + sequence catch-up + recent audit events | 图谱任务在内存 TaskManager；模拟状态落文件 | 当前实时恢复机制保留；再补可重启的 Session 索引 |
| 真值约束 | confidence cap、unknown、Policy reason code、Live fail-closed | 面向开放式推演，重点是图谱/模拟与报告 | 不采用“预测万物”式表述 |
| 外部依赖 | Replay 可完全离线；OpenAI 可回退 Mock | LLM API、Zep Cloud、OASIS 是主要依赖 | 最终现场 Demo 继续以可离线 Replay 兜底 |
| 许可 | 当前项目自身许可需由发布者确定 | MiroFish 为 [AGPL-3.0](https://github.com/666ghj/MiroFish/blob/b5b53acc57189a4a42e44a23e149dc655c98fe82/LICENSE) | 只借鉴信息架构；复制其代码前必须单独做许可证评审 |

MiroFish 关键源码入口：

- [官方 README / 五步工作流](https://github.com/666ghj/MiroFish/blob/b5b53acc57189a4a42e44a23e149dc655c98fe82/README.md#-workflow)
- [GraphBuilderService / Zep 图谱构建](https://github.com/666ghj/MiroFish/blob/b5b53acc57189a4a42e44a23e149dc655c98fe82/backend/app/services/graph_builder.py)
- [SimulationManager / OASIS 双平台模拟](https://github.com/666ghj/MiroFish/blob/b5b53acc57189a4a42e44a23e149dc655c98fe82/backend/app/services/simulation_manager.py)
- [ReportAgent](https://github.com/666ghj/MiroFish/blob/b5b53acc57189a4a42e44a23e149dc655c98fe82/backend/app/services/report_agent.py)
- [MainView / Step 1–5 与分屏模式](https://github.com/666ghj/MiroFish/blob/b5b53acc57189a4a42e44a23e149dc655c98fe82/frontend/src/views/MainView.vue)
- [TaskManager / 长任务进度](https://github.com/666ghj/MiroFish/blob/b5b53acc57189a4a42e44a23e149dc655c98fe82/backend/app/models/task.py)

## 最终 Demo 的最优交互上限

前端的上限不是“更像监控画面”，而是成为一台可解释、可回放、可降级的
空间信号仪器。推荐主流程只保留四步：

1. **Ready**：选择 Live / Replay，显示拓扑、标定、两个 RX 和诚实的 readiness。
2. **Observe**：首屏只展示三信号、抽象推断场和一句受限结论。
3. **Why**：点击结论展开 Evidence → Agent 分歧 → Policy 拒绝；默认不铺满全部卡片。
4. **Replay**：时间轴跳到关键事件，验证同一 evidence hash 可复现。

桌面端建议“主舞台 + 右侧结论抽屉 + 底部时间轴”；移动端建议“结论摘要 →
三信号 → 推断场 → 可展开 Why”，不要默认渲染整段 Council 和全部 Evidence。
Story 只作为固定视觉验收入口，必须标记 `story · simulated`，不得显示实时连接
故障或可用的录制控制。

### 前端依赖决策

主页使用已锁定版本的 `lenis@1.3.26` 统一长页的滚轮、锚点和路由惯性。
原生 CSS `scroll-behavior` 无法为路由切换提供可控的停止与惯性边界；该依赖仅作用于
视图滚动，不进入传感、Council 或数据合约。`prefers-reduced-motion` 和用户的
“减少动态”设置会关闭平滑轮滚、将插值设为即时，并由真实浏览器用例验收。

## 后续优先级

### P0：形成可同步的 Replay 检查点

- 完成 60 分钟 Soak、完整 Release gate 和版本 manifest。
- 提交 `phase12/demo-hardening`；GitHub 只推绿色检查点。
- Replay manifest 允许 simulated profile，但必须给出警告；Final manifest 必须
  要求 Live bundle、非模拟 profile、固件哈希和五份硬件报告。

### P1：`feat/frontend-v2`

- 把 Observe/Why/Replay 变成渐进披露主流程。
- 移动端首屏优先一句结论、信号状态和推断场，Council 详情折叠。
- 增加阶段式 Demo rail：Ready → Observe → Explain → Reproduce。

### P1：`hardware/live-validation`

- 三块 ESP32 的角色、端口、固件哈希、房间拓扑与 5 点纵深轴落档。
- 完成 recorded、non-simulated 标定与 held-out 指标。
- 30 分钟 Live 稳定性和 Live-vs-Replay 对照。

### P2：空间状态索引与外部执行器

- 先做 SQLite/Parquet 级 Session/Evidence 索引，再决定是否需要更重数据库。
- 灯光/机械输出必须走独立安全适配层；Agent 只能提出受限意图，不能直接驱动设备。
