# 产品规格：WiFi Spatial Council

## 1. 产品一句话

把不可见的 Wi-Fi 信道变化转译成三个诚实、可校准的空间代理量，再让多个 Agent 对同一份证据提出解释、反证和争议，最终以实时图形、文字和声音呈现一个“空间正在发生什么”的推断场。

## 2. 演示目标

面向黑客松、艺术科技展、投资人或研发评审，在 2 分钟内完成以下体验：

1. 展示空场标定后的稳定基线。
2. 一个人从远端走向近端，三项数据实时变化。
3. 多个 Agent 独立分析并出现真实分歧，例如“人体移动”与“无线干扰/家具变化”两种解释。
4. 怀疑者要求验证；主持人将结果标为 supported、ambiguous 或 unavailable。
5. Web 中的抽象信号雕塑和声景随数据变化，但始终提示它不是摄像画面。
6. 切换到 Replay，完整复现刚才的原始数据、Agent 记录和最终结果。

## 3. 用户价值

- 技术价值：展示低成本 CSI 的采集、标定、回放、推理与审计闭环。
- Agent 价值：争论用于发现替代解释和越权结论，而不是制造“多数投票即真实”。
- 审美价值：不增加伪信息，用抽象运动、层次、密度和声音把三个标量变成丰富体验。
- 工程价值：即便硬件暂未接入，Web、Agent、测试和演示仍可用相同契约完成。

## 4. MVP 范围

### 必须完成

- 1 TX + 2 RX 真机采集，以及单 RX 降级。
- Mock、Replay、Live 三种数据源。
- 原始数据不可变录制、校验和、版本信息和回放。
- 三项代理量及独立的质量/置信字段。
- 确定性质量门和 Policy Arbiter。
- 专家、红队与综合 Agent 的有限轮次争论。
- 实时 WebSocket、证据页、争论页和回放页。
- 抽象数据视觉、Web Audio 声景、结果快照。
- 无 API、掉板、丢包、标定不匹配等降级路径。

### 明确不做

- 身份、人数、姿态、健康、危险行为判断。
- 摄像机式图像、人体轮廓、真实热力图。
- 绝对墙体密度、墙材质或墙后目标断言。
- 未经现场标定的米制深度、ToF、AoA、TDoA。
- 将 Intel 5300、Nexmon、PicoScenes 或公开数据集精度直接迁移到 ESP32。
- 用合成数据代替真机验收。

## 5. 三项对外数据

| 中文名 | 字段 | 更新 | 状态 | 含义 |
| --- | --- | --- | --- | --- |
| 活动强度 | `motion_intensity` | 4–10 Hz | idle / micro / moving / fast / unknown | 当前窗口信道变化的动态强度 |
| 遮挡/空间占用代理 | `occupancy_density_proxy` | 2–4 Hz | low / medium / high / unknown | 相对空场基线的扰动覆盖程度，不等于人数 |
| 空间纵深代理 | `depth_zone_proxy` | 2–4 Hz | near / mid / far / unknown | 沿已标定轴的相对传播纵深，不等于米制距离 |

每个输出必须同时携带：测量质量、模型支持、更新时间、状态、失效原因和证据引用。不得把三者合并成一个“神奇分数”。

## 6. 产品状态

### Session

`CREATED → PRECHECK → CALIBRATION_REQUIRED | READY → RUNNING ↔ PAUSED → STOPPING → STOPPED`

同时携带 `healthy | degraded | stale | error` 健康状态。切换数据源必须新建 Session，禁止在同一周期混入不同来源。

### Analysis cycle

`OPEN → EVIDENCE_SEALED → QUALITY_GATED → SPECIALISTS → CROSS_EXAMINATION → RESPONSES → POLICY_VALIDATED → SYNTHESIZED → RENDERED → COMMITTED`

质量失败时走：`QUALITY_GATED → NO_INFERENCE → RENDERED → COMMITTED`。

## 7. 功能需求

- FR-01：系统能从两个独立 RX 接收、校验、配对并持久化 CSI 包。
- FR-02：同一录制在 Replay 中重新计算，确定性结果可复现。
- FR-03：硬件缺席时 Mock 和 Replay 能覆盖完整 UI 与 Agent 流程。
- FR-04：原始帧、窗口、三信号、证据包、Agent 主张和 Web 事件均有版本化 schema。
- FR-05：每一项最终主张能追溯到单个 `evidence_hash`。
- FR-06：Agent 只能引用证据，不能新造测量值或提升置信度。
- FR-07：只剩一个 RX 时纵深自动变为 unknown，其他链路继续。
- FR-08：LLM 不可用时确定性信号、基线结论与 Web 仍持续运行。
- FR-09：Web 支持开始、暂停、停止、录制、回放、倍速与拖动。
- FR-10：所有视觉结果带“推断场/非真实影像”标签，声音默认静音。

## 8. 非功能需求

- NFR-01：信号到 Web 曲线的 p95 端到端延迟目标 <300 ms。
- NFR-02：Replay 模式在普通开发机上稳定 60 FPS 视觉；数据更新率独立标注。
- NFR-03：Agent 周期不阻塞信号链；一个周期目标 <8 s，15 s 强制降级。
- NFR-04：30 分钟真机采集无重启、无失控队列。
- NFR-05：60 分钟 Web+后端 soak 无崩溃；内存增长目标 <10%。
- NFR-06：任何 API 密钥只存在服务端环境变量中。
- NFR-07：原始 CSI 默认只在本机保存，配置保留期，导出时去除真实 MAC。

## 9. 成功定义

项目成功不等于“画面看起来像成像”，而是同时满足：

1. Replay 全链路可复现并通过故障注入。
2. 三项代理量在指定房间、指定布置、留出测试轮次中达到 `ACCEPTANCE_TESTS.md` 的门槛。
3. 达不到时系统明确拒绝或降级，没有被 Agent 语言掩盖。
4. 观众能在 2 分钟内理解“测量、推断、争议、艺术化表达”四个层次。

