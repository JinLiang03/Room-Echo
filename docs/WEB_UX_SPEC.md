# Room Echo 单一 Agent Web 体验

## 1. 体验定位

视觉主体沿用当前前端的**彩色数字生成式推断场**，而不是监控界面或伪人体热成像。新版首页不替换中心数字动画：它被放在右侧作为持续更新的实时推断场，同时移除四周循环数字外框；左侧只展示一个 Room Echo Agent 的实时解释，下方毛玻璃窗口固定显示四项受限建议。

首页数字组成的椅子、桌面、拱门、花园、穹顶都是**生成式视觉主题**：可以由用户预览，也可以由通过 Policy 的 Fusion 结果从白名单中选择。它们不是由 CSI 推断出的房间、家具、人物或现场轮廓；主题几何不得写入 `SignalTriplet`、Evidence、Agent claim 或行动决策。

永久水印：

```text
INFERENCE FIELD — NOT A CAMERA IMAGE
艺术化代理信号解释，非真实影像
```

## 2. 信息架构

公开层只有三个主入口：

1. **此刻 / Home**：默认是一页连续的加速养老模拟日；左侧一个简洁 Room Echo Agent 卡与 2×2 四反应窗口，右侧是由同一时刻代理快照驱动的实时彩色数字推断场；来源和 truth boundary 沿用现有位置。
2. **记忆 / Replay**：保留原有回放控制、事件时间线与局部视觉书签，只统一为首页的毛玻璃视觉。
3. **为什么 / Why**：保留原有当前判断、主要质疑、解释置信与传感上限，只统一为首页的毛玻璃视觉；普通访问不展开七角色。

七角色的主张、挑战、回应/让步与 Policy 拒绝只在 debug 或 `?audit=1` 的**内部审议记录**中展开。Observe、Evidence、Story、Perf 和 Settings 仍作为工程验证/辅助路由保留，不与公开 Agent 并列。

## 3. 桌面布局

- 首页首屏约按 **31% / 69%** 分栏：左侧是解释与行动，右侧是现有数字推断场。
- 左栏顶部：Room Echo 品牌，以及“此刻 / 记忆 / 为什么”三个导航；来源只占用参考图底部原有的微型系统行，不增加徽标或场景导航。
- 左栏主卡：唯一公开 Agent 的简洁状态与实时解释；保持参考图的单卡密度，不在卡片周围增加人物、户型、时间线、场景来源或 `SPACE / CONTEXT / INPUT` 区块。
- 左栏下方毛玻璃窗口：以 2×2 网格固定显示四个简短反应 tile；每格只保留图标、名称与紧凑状态，至少一格使用现有数字形态之一作为生成式生物图标，并以 ARIA 说明“非物种识别”。
- 右栏：Canvas 2D 中心彩色数字主题由当前 care 时刻的 hash-bound `proxy_triplet` 保持实时动画；四周循环数字外框关闭，顶部显示推断场状态，底部永久显示非摄像水印。
- 首页不再显示全局七角色列表、Agent agreement 列或七个角色状态 footer；这些只属于 audit。

Home、Memory、Why 共用半透明浅色面板、背景模糊、细边框、柔和阴影与相同标题/导航体系，避免从首页进入二级页后回到旧仪表盘视觉。Memory 与 Why 只换材质、间距、字体和导航状态，不新增 care 卡片或改变原有内容结构。毛玻璃不能用模糊遮盖来源或状态文字。

移动端按“品牌/来源 → 单一 Agent → 行动回执 → 数字推断场”纵向排列；证据密集表格和七角色审议不强塞主屏。

## 4. 精确视觉映射

| 数据 | 视觉参数 | 规则 |
| --- | --- | --- |
| 用户主题选择 | 家具/空间主题几何 | 只改变生成视觉模板；明确标记“非检测物体”，不改变任何传感值 |
| Fusion 视觉选择 | 户型/座椅/灯具/拱门等主题与形态过渡 | 只改变白名单生成模板；明确标记“非检测物体”，不改变任何传感值或置信度 |
| pointer/touch | 局部排斥、形变 | 只改当前 Canvas 像素，不改变主题语义、三信号或置信度 |
| motion 0–1 | 数字漂移速度、脉冲频率、形变速度 | 低值缓慢呼吸，高值加快；不决定物体或空间类别 |
| occupancy low/high | 体积密度、颗粒数量、透明度、折射扰动 | 越高越稠密，但空间边界保持抽象 |
| depth near/mid/far | Z 层间距、透视缩放、焦点层 | 用层次表现相对纵深；unknown 时层次塌缩并灰化 |
| measurement quality | 饱和度、边缘锐度、噪声 | 低质量降饱和并扩散，不以红色伪装危险 |
| disagreement | 两组相位不同的细环/波纹 | 只表达解释分歧，不改变三信号值 |
| unavailable | 静态主题骨架 + 中性数字散点 + 原因 | 清除所有信号驱动的速度/密度/层次；保留的主题只代表生成式视觉选择，不是检测结果 |

渲染使用 Canvas 2D 的确定性参数映射。普通 Wi-Fi 模式以同一 `SignalTriplet` + `CouncilResult` + theme + seed 得到可复现视觉；默认 care 模式以当前 `SimulatedCareMoment` 内 hash-bound `proxy_triplet` + theme + seed 得到可复现视觉。不要依赖每周期生成图片；GIF 只用于评审/传播，绝不作为实时渲染源。

数字形态不表示人物、跌倒、路径、夜间状态或长期习惯。即使主题看起来像家具或空间结构，也只能称为生成式主题或推断场。

## 5. 单一 Agent 与行动窗口

普通 Wi-Fi 模式的公开 Agent 使用最新 cycle 的封存 `signal_snapshot`；默认 care 模式使用当前时刻 hash-bound Mock `proxy_triplet`，并与四行动和右侧数字场共享 evidence hash、session 与 window：

- `waiting`：没有足够信号，不补结论；
- `observing`：解释三项代理状态，等待 Evidence 封存；
- `checking`：内部 challenge 未解决，明确还不行动；
- `responding`：显示通过 Policy 的统一解释；
- `unknown`：stale/offline/unavailable，清空旧的“此刻”解释。

普通 Wi-Fi 模式的第一项行动只读 `CouncilResult.action_decision`：

- `ambient_light_preview + simulated_preview`：仅在 Mock/Replay 中显示三段环境引导光预演，并标注“模拟预览 · 未连接真实设备”；
- `wait_and_observe + withheld`：证据有歧义或降级，显示“继续观察 / 已暂缓”；
- `stay_silent + withheld`：证据不足、契约失败或 Live 无执行器，显示“保持安静 / 已暂缓”。

窗口始终补足四个位置，使用户能同时看到当前确定性决定、延长观察、人类复核和设备协同接口的状态；没有可验证合约的槽位显示“尚未启用”，不能伪装为已建议或已执行。

默认 `#/home` 一次取得完整 `simulated-care-scenario.v2`，从日常开始，每 8 秒按日常、卫生间超时、人工跌倒演练、夜间宠物外部标签自动循环；不切页、不改 URL、不重复请求。`?care=routine|bathroom_timeout|fall_drill|pet_night` 仅指定确定性初始帧。当前 `SimulatedCareMoment` 的 `suggestions` 投影到同一四个反应 tile：

1. 环境光预演；
2. 语音询问脚本；
3. 家属消息草稿；
4. 机器人查看任务预演。

每张卡只能显示 `模拟预览` 或 `已暂缓`，并明确“未连接设备 / 未发送消息 / 未创建任务”。当前 UI 不存在真实执行成功状态，也不接入灯具、音箱、通知服务或机器人。左侧 Agent、四卡与右场共享当前 `care-evidence-core.v2` 的 evidence hash、session 与 window；行动动画不能改变正式三代理信号、Evidence 或 Council 置信。

### 5.1 后端养老模拟边界

`SimulatedCareScenario` 保留为只读、确定性的后端 fixture，用于测试通俗结论和四项行动意图。公开前端不增加场景 selector、独立信息模块、`SPACE / CONTEXT / INPUT`、虚构老人卡、户型卡、全天时间线或“已知 / 未知 / 来源”三栏。默认首页只复用一个 Agent 卡、同一 2×2 四反应窗口和右侧数字场；底部微型系统行标记 `SIM · CARE` 与 `NO DEVICE EXECUTION`。每个 `care-evidence-core.v2` 内嵌唯一 Mock `proxy_triplet` 并纳入 canonical hash；malformed、unknown 或必需外部观察/代理降级时，三处一起回到 waiting/unavailable，四行动保持 withheld，且不得借用 Replay 状态。

fixture 中的人物、房间、宠物与跌倒字段仍必须携带 simulation / external / drill provenance，Wi-Fi 单独不能得出这些结论。该 provenance 是合约与审计边界，不是要求新增前台资料模块。

## 6. 声音映射

Web Audio 声音默认静音，用户点击后启用：

- motion → tempo/脉冲密度；
- occupancy → filter cutoff 与谐波厚度；
- depth → reverb time 与立体声宽度；
- measurement quality → 干湿比与高频清晰度；
- disagreement → 极轻的拍频，不使用警报音。

声音参数平滑插值，避免跳变；网页失焦或 Session 停止时渐隐。提供全局静音和减少动态。

## 7. 置信呈现

不得出现一个混合“AI 可信度”。公开 Agent 至少并列显示：

- 最终解释置信 `display_confidence`；
- 传感器置信上限 `sensor_confidence_cap`。

并保证前者不高于后者。内部 Why/audit 可进一步并列：

- 测量质量 `measurement_quality`；
- 模型支持度 `model_support`；
- 推理一致性 `interpretation_agreement`，以文本/计数显示。

例如：“解释 61%｜传感上限 68%”。内部 audit 可显示：“测量质量 0.68（degraded）｜模型支持 0.61｜3 项主张一致，2 项仍有分歧”。行动置信另满足 `decision_confidence <= sensor_confidence_cap`，不能用解释一致度加分。

## 8. 内部 Council audit

仅在 debug 或 `?audit=1` 中按周期和阶段分组：

- Proposed：角色头像/色点、主张、evidence chips、替代解释。
- Challenged：挑战类别、severity、证据和解除测试。
- Revised/Conceded：修改前后短摘要。
- Policy：被拒绝内容和公开原因。
- Final：accepted、ambiguous 或 unavailable。

只展示简短 reasoning summary，不显示隐藏思维链。无引用或无效引用的内容标记为 rejected，不得进入最终卡。这个页面解释单一 Room Echo Agent 的审议依据，不代表前台有七个 Agent。

## 9. Evidence 页面

- 三项原始估计/滤波曲线、阈值和 unknown 区段。
- RX-A/B packet rate、丢包、配对、RSSI/noise、干扰、OOD。
- 当前拓扑图和 calibration match。
- 当前 EvidencePacket 的版本、hash、feature refs 和 provenance。
- measured / inferred / generated / simulated 图例永久可见。

## 10. Replay

- 录制列表与 manifest 摘要。
- 播放、暂停、单步、0.25×/0.5×/1×/2×/4×、拖动。
- 事件标记与 Agent 周期标记。
- `recompute=true` 状态提示。
- ground truth 默认隐藏，只在评估模式显示，且明确不进入 Agent。

## 11. 动画和可访问性

- 渲染目标 60 FPS；数据采样率另行显示，不能用插值动画假装更多测量。
- 所有状态同时用文字、图标和颜色。
- `unknown` 用灰色；error 用克制的橙/红，并附原因。
- 支持键盘、焦点、ARIA、色弱安全对比和 `prefers-reduced-motion`。
- 断线后显示 stale overlay；恢复前停止所有信号驱动的自动动画。手选主题和指针预览仍可用，但必须同时显示 `unknown` 与“只改变视觉”。
- 行动状态不能只靠颜色区分；`模拟预览`、`已暂缓`、原因与是否连接真实设备必须有文字。

## 12. 2 分钟演示脚本

以 `docs/DEMO_SCRIPT.md` 为唯一逐镜脚本。公开演示从默认 `SIM · CARE` 首页开始，在同一页面依次呈现日常、卫生间超时、人工跌倒演练与夜间宠物外部标签；每次自动切换都同步更新一个 Agent、四反应 tile 和同源数字场。随后打开“记忆”与“为什么”确认原信息架构，最后以 `SIM · CARE`、`NO DEVICE EXECUTION`、非摄像水印和 unknown/withheld 边界收尾。
