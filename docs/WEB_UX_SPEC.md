# Web 演示与多模态体验

## 1. 体验定位

视觉是“数字生成式推断场”，而不是监控界面或伪人体热成像。首页采用暖象牙纸色、钴蓝数字、珊瑚、薄荷与奶油黄；Observe/Evidence 继续保留可审计的数据密度，但统一使用清新、低噪声的编辑式层级。

首页的椅子、桌面、拱门、花园、穹顶都是**生成式视觉主题**：可以由用户预览，也可以由通过 Policy 的 Fusion 结果从白名单中选择。它们不是由 CSI 推断出的房间、家具或现场轮廓；主题几何不得写入 `SignalTriplet`、Evidence 或 Agent claim。

永久水印：

```text
INFERENCE FIELD — NOT A CAMERA IMAGE
艺术化信号解释，非真实影像
```

## 2. 信息架构

首页加六个主视图：

1. **Home**：数字家具主题、三项代理短读数、明确的数据来源与 truth boundary。
2. **Observe**：三信号、实时场、当前结论、最重要替代解释。
3. **Council**：按轮次的主张、证据、挑战、回应/让步、策略拒绝。
4. **Evidence**：曲线、丢包、同步、干扰、OOD、标定和拓扑。
5. **Replay**：录制、传输控制与事件时间线。
6. **Story/Settings**：固定状态验收与无障碍/音频偏好。

Replay 以底部时间轴或独立页呈现；设置面板含源、串口、音频、减少动态、数据导出和标定。

## 3. 桌面布局

- 首页首屏：左侧占最大面积的数字主题场，右侧三代理信号与 Agent agreement 独立列，底部是五个主题的字符预览目录。
- 顶栏：Live/Replay、Session、TX/RX 在线数、信道/带宽、标定、最新帧、Start/Pause/Stop/Record。
- 左列：三张信号卡；显示值、状态、测量质量、模型支持、更新时间。
- 中央：占页面最大面积的抽象信号雕塑。
- 右列：当前结论、替代解释、限制、Agent 周期状态。
- 底栏：时间线、事件标记、回放速度和数据新鲜度。

移动端按：状态 → 三卡 → 信号雕塑 → 结论 → 争论摘要 → 时间线排列。证据密集表格不强塞主屏。

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

渲染使用 Canvas 2D 的确定性参数映射；同一 `SignalTriplet` + `CouncilResult` + theme + seed 必须得到可复现视觉。不要依赖每周期生成图片；GIF 只用于评审/传播，绝不作为实时渲染源。

## 5. 声音映射

Web Audio 声音默认静音，用户点击后启用：

- motion → tempo/脉冲密度；
- occupancy → filter cutoff 与谐波厚度；
- depth → reverb time 与立体声宽度；
- measurement quality → 干湿比与高频清晰度；
- disagreement → 极轻的拍频，不使用警报音。

声音参数平滑插值，避免跳变；网页失焦或 Session 停止时渐隐。提供全局静音和减少动态。

## 6. 三个分数并列

不得出现一个混合“AI 可信度”。同一结果并列显示：

- 测量质量 `measurement_quality`；
- 模型支持度 `model_support`；
- 推理一致性 `interpretation_agreement`，以文本/计数显示。

例如：“测量质量 0.68（degraded）｜模型支持 0.61｜3 项主张一致，2 项仍有分歧”。

## 7. Council 页面

以周期和阶段分组：

- Proposed：角色头像/色点、主张、evidence chips、替代解释。
- Challenged：挑战类别、severity、证据和解除测试。
- Revised/Conceded：修改前后短摘要。
- Policy：被拒绝内容和公开原因。
- Final：accepted、ambiguous 或 unavailable。

只展示简短 reasoning summary，不显示隐藏思维链。无引用或无效引用的内容标记为 rejected，不得进入最终卡。

## 8. Evidence 页面

- 三项原始估计/滤波曲线、阈值和 unknown 区段。
- RX-A/B packet rate、丢包、配对、RSSI/noise、干扰、OOD。
- 当前拓扑图和 calibration match。
- 当前 EvidencePacket 的版本、hash、feature refs 和 provenance。
- measured / inferred / generated / simulated 图例永久可见。

## 9. Replay

- 录制列表与 manifest 摘要。
- 播放、暂停、单步、0.25×/0.5×/1×/2×/4×、拖动。
- 事件标记与 Agent 周期标记。
- `recompute=true` 状态提示。
- ground truth 默认隐藏，只在评估模式显示，且明确不进入 Agent。

## 10. 动画和可访问性

- 渲染目标 60 FPS；数据采样率另行显示，不能用插值动画假装更多测量。
- 所有状态同时用文字、图标和颜色。
- `unknown` 用灰色；error 用克制的橙/红，并附原因。
- 支持键盘、焦点、ARIA、色弱安全对比和 `prefers-reduced-motion`。
- 断线后显示 stale overlay；恢复前停止所有信号驱动的自动动画。手选主题和指针预览仍可用，但必须同时显示 `unknown` 与“只改变视觉”。

## 11. 2 分钟演示脚本

- 0:00–0:15：Replay 或 Live ready，展示空场稳定和硬件拓扑。
- 0:15–0:40：远端进入，motion 上升、depth 从 far 向 mid，视觉层次推进。
- 0:40–1:05：靠近/增加遮挡，occupancy 变化；Agent 专家并行出现。
- 1:05–1:30：RedTeam 提出门/干扰替代解释，一项主张修订或让步。
- 1:30–1:45：Policy Arbiter 拒绝一个越权结论，Fusion 输出带限制的结果。
- 1:45–2:00：切 Replay、拖动到关键事件，证明结果可复现和可审计。
