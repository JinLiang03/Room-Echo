# 产品规格：Room Echo（Wi-Fi Spatial Council）

## 1. 产品一句话

把不可见的 Wi-Fi 信道变化转译成三个诚实、可校准的空间代理量；前台由一个 Room Echo Agent 实时解释“知道什么、还不知道什么”，并给出有边界的行动回执，七个专业角色只在后台完成反证与审计。右侧彩色数字场是代理信号驱动的**实时推断场**，不是摄像画面。

## 2. 演示目标

面向黑客松、艺术科技展、投资人或研发评审，在 2 分钟内完成以下可复现体验。默认首页是确定性 Mock 养老工作流，不冒充真实硬件现场能力或真实照护验证：

1. 默认 `#/home` 明确显示 `SIM · CARE`，一次加载同一虚构日的四个时刻，并每 8 秒自动循环。
2. 右侧中心彩色数字场随当前时刻的 Mock 三代理快照连续变化，移除四周循环数字外框，同时永久标注 `INFERENCE FIELD — NOT A CAMERA IMAGE`。
3. 左侧只出现一个 Room Echo Agent，按“观察 → 解释 → 复核 → 回应/未知”说明与右场同一证据时刻。
4. 下方毛玻璃窗口以 2×2 四个简短反应 tile 展示同一时刻的受限建议；只显示现有行动状态，不增加场景资料或说明模块。
5. 需要审计时再打开内部 Council，检查七个角色的证据引用、挑战、让步和 Policy 拒绝；角色数量不抬高置信度。
6. 打开 Memory 使用 Replay 拖动或重播封存数据；其原有控制、时间线与视觉书签不被 care fixture 改写。

## 3. 用户价值

- 技术价值：展示低成本 CSI 的采集、标定、回放、推理与审计闭环。
- Agent 价值：用户只需面对一个持续、可理解的 Agent；内部争论用于发现替代解释和越权结论，而不是制造“多数投票即真实”。
- 审美价值：不增加伪信息，用抽象运动、层次、密度和声音把三个标量变成丰富体验。
- 交互价值：Agent 不只解释，还给出“模拟预览”或“暂缓”的可见行动回执，让判断与反应形成闭环而不伪装真实执行。
- 工程价值：即便硬件暂未接入，Web、Agent、测试和演示仍可用相同契约完成。
- 场景价值：后端用明确标记的合成照护 fixture 验证“何时询问、何时不打扰、何时交给人确认”的行动边界，不把这些合成资料扩展成新的前台信息模块。

## 4. MVP 范围

### 必须完成

- 1 TX + 2 RX 真机采集，以及单 RX 降级。
- Mock、Replay、Live 三种数据源。
- 原始数据不可变录制、校验和、版本信息和回放。
- 三项代理量及独立的质量/置信字段。
- 确定性质量门和 Policy Arbiter。
- 专家、红队与综合 Agent 的有限轮次争论。
- 前台单一 Room Echo Agent；七角色 Council 仅作为内部审议和显式 audit 视图。
- 基于封存 Evidence 与 Policy 结果生成的确定性 `AgentActionDecision`。
- 实时 WebSocket、证据页、内部审计页和回放页。
- 现有彩色数字推断场、Web Audio 声景、结果快照和行动小窗口。
- 独立的后端 `simulated-care-scenario.v2` 养老演示层：匿名虚构人物、58㎡ 六区户型、13 条 24 小时脚本、四个确定性时刻、每时刻一个 hash-bound Mock `proxy_triplet` 和固定四项受限建议；默认 Home 一次加载并每 8 秒循环，不新增公开场景选择器或资料卡。
- 无 API、掉板、丢包、标定不匹配等降级路径。

### 明确不做

- 身份、人数、姿态、健康、危险行为判断。
- 由当前 Wi-Fi CSI 推断人物、跌倒、路径、夜间状态、宠物、具体房间、长期习惯或作息。
- 摄像机式图像、人体轮廓、真实热力图。
- 绝对墙体密度、墙材质或墙后目标断言。
- 未经现场标定的米制深度、ToF、AoA、TDoA。
- 将 Intel 5300、Nexmon、PicoScenes 或公开数据集精度直接迁移到 ESP32。
- 用合成数据代替真机验收。
- 在当前 Mock/Replay 中声称触发了真实灯具或其他外部设备。

养老演示不改变以上边界：人物、户型、全天活动、区域、宠物和跌倒均来自明确标记的 synthetic fixture、模拟外部标签或人工演练标签；每帧内嵌的 Mock Wi-Fi `proxy_triplet` 只以三项代理量旁证变化，并非现场采集。它是工作流与交互验证，不是照护效果、跌倒检测或宠物识别能力验证。

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
- FR-11：首页只展示一个 Room Echo Agent；五个 proposer、skeptic 和 fusion 仅在显式 audit 中展开。
- FR-12：行动决策只能由当前封存 Evidence、来源模式、质量门和确定性 Policy 状态生成；Provider 自由文本不能选择或修改行动。
- FR-13：Mock/Replay 只允许 `simulated_preview` 或 `withheld`；Live 在没有单独验证的执行器适配器时必须 `withheld`。
- FR-14：Wi-Fi Council 行动解释不得推断人物、跌倒、宠物、房间、路径、夜间状态或长期习惯；证据不足时必须保持静默或继续观察。
- FR-15：`GET /api/care/scenario?moment=...` 必须一次返回同一确定性虚构日的 13 条时间线、四个时刻和选中索引；合约为 `simulated-care-scenario.v2`，且永久携带 `simulation_only=true`、`source_mode=mock`、`device_execution_enabled=false`。
- FR-16：养老场景的匿名人物为 75—79 岁模拟独居者；58㎡ 户型固定为玄关、客厅、卧室、厨房、卫生间、阳台六区，所有人物/区域/面积不得写成 Wi-Fi 推断结果。
- FR-17：四个养老时刻固定为日常、卫生间 31 分钟超过 20 分钟阈值、人工跌倒风险演练、02:18—02:22 外部宠物标签；没有对应外部标签时不得得出房间、宠物或跌倒结论。
- FR-18：每个养老时刻固定返回环境光、语音询问、家属消息草稿、机器人查看四项建议；每项只能为 `simulated_preview` 或 `withheld`，不得出现 executed/completed，且 `action_confidence <= conclusion_confidence <= sensor_confidence_cap`。
- FR-19：默认 `#/home` 必须一次加载完整 care v2 场景，从日常开始按固定顺序每 8 秒连续轮播；一个时刻的通俗结论、四项 suggestions 与 `care-evidence-core.v2` 内 hash-bound Mock `proxy_triplet` 必须原子投影到一个 Room Echo Agent、同一 2×2 四反应窗口和右侧数字场。不得新增人物、户型、时间线、输入来源或场景选择模块，不得写回正式 `SignalTriplet`、`EvidencePacket` 或 Council 置信；`?care=...` 只指定确定性初始帧。
- FR-20：care payload malformed、`interpretation_status=unknown`，或必需外部观察/`proxy_triplet` 降级时，Agent、四行动与右场必须共同回到 waiting/unavailable，四行动全部 withheld，且不得借用 live/replay 数据补全。

## 8. 非功能需求

- NFR-01：信号到 Web 曲线的 p95 端到端延迟目标 <300 ms。
- NFR-02：Replay 模式在普通开发机上稳定 60 FPS 视觉；数据更新率独立标注。
- NFR-03：Agent 周期不阻塞信号链；一个周期目标 <8 s，15 s 强制降级。
- NFR-04：30 分钟真机采集无重启、无失控队列。
- NFR-05：60 分钟 Web+后端 soak 无崩溃；内存增长目标 <10%。
- NFR-06：任何 API 密钥只存在服务端环境变量中。
- NFR-07：原始 CSI 默认只在本机保存，配置保留期，导出时去除真实 MAC。
- NFR-08：`decision_confidence <= sensor_confidence_cap`，且行动的 cycle、evidence hash 与最终 CouncilResult 必须完全一致。

## 9. 成功定义

项目成功不等于“画面看起来像成像”，而是同时满足：

1. Replay 全链路可复现并通过故障注入。
2. 三项代理量在指定房间、指定布置、留出测试轮次中达到 `ACCEPTANCE_TESTS.md` 的门槛。
3. 达不到时系统明确拒绝或降级，没有被 Agent 语言掩盖。
4. 观众能在 2 分钟内理解“代理测量、单一 Agent 解释、受限行动、内部审计、艺术化表达”五个层次。
5. 后端审计能区分 synthetic fixture、模拟外部标签与 Mock Wi-Fi 三代理旁证；观众能看懂左 Agent、四动作与右动画来自同一 hash-bound 时刻。公开首页不靠新增资料模块解释这些层级，也不把模拟场景写成真实老人监测或真实设备执行。
