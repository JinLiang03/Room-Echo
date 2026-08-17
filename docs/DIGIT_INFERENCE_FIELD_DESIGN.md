# Digit Inference Field — 前端方案

## Outcome

在不修改后端、WS 协议、估计器或 Agent 置信链的前提下，新增一个可独立运行的 `Home` 首页：数字字符组成持续变化的虚拟家具/空间主题，并直接消费现有 `SignalTriplet` 与 `CouncilResult`。

设计母版：`artifacts/design/digit-inference-field-homepage-v1.png`（1536×1024，sha256 `a3c703f2f6e9f45f8d5eb557f22b552801946d90778935ac4d9fc148935a2f21`）。生成提示词保存在同目录的 `.prompt.md`。

## Truth boundary

- 永久显示 `INFERENCE FIELD — NOT A CAMERA IMAGE`。
- 椅子/桌面/拱门/花园/穹顶是白名单生成主题，可由用户预览或由通过 Policy 的 Fusion 结果选择；不是系统识别到的真实物体、房间或布局。
- 鼠标/触摸只改变 Canvas 视觉形变，不写回三项代理信号、质量、置信度或 Agent 状态。
- occupancy 只叫“占用/遮挡密度代理”，绝不显示人数。
- depth 只叫“相对纵深区域代理”，绝不显示米制距离。
- 当前 `measurement_quality` 单独展示；`CouncilResult.sensor_confidence_cap` 与同一结果的 `final claim confidence` 成对展示，`interpretation_agreement` 另列，禁止跨窗口拼接置信数字。
- stale/unknown 清除所有信号驱动参数；只保留明确标为“static theme preview”的用户主题骨架。

## Visual system

| Token | Value | Role |
| --- | --- | --- |
| paper | `#f5f0e6` | 页面与 Canvas 背景 |
| cobalt | `#2457d6` | 数字主体、导航、边界 |
| coral | `#f27f75` | motion |
| mint | `#43aa94` | occupancy proxy |
| butter | `#d9a323` | depth-zone proxy |
| violet | `#7765cf` | soundscape / interpretation |
| line | `#d8d1c4` | 1px 结构线 |

UI 使用系统 sans + monospaced 数字；避免暗色赛博 HUD、玻璃拟态、热成像、摄影背景和高密度卡片墙。

## Contract mapping

| Input | Visual output | Guardrail |
| --- | --- | --- |
| `motion.value` | 字符漂移速度、脉冲、morph 速度 | 不选主题，不生成类别 |
| occupancy probabilities | 可见字符比例、填充稠密 | 不表示人数 |
| depth probabilities | 相对 Z 层距与轻微视差 | 不表示距离或几何重建 |
| min signal confidence | 饱和、透明、扩散 | 不与 Agent agreement 混合 |
| Council disagreement | 独立虚线相位弧 | 不改变三信号数字 |
| user/Fusion theme | 等点数目标模板与主题过渡 | 只改变生成视觉；不写回传感器、Agent 证据或置信度 |
| pointer/touch | 有边界的局部排斥 | 不触发数据 action |

数据路径保持：`WebSocket → StreamProvider → state.triplet/result → mapRenderParams(multimodal-v1) → DigitMorphField(digit-field-v1)`。音频仍消费原 `multimodal-v1`，新首页不改变声音合约。

## Five themes and agent visual assets

| Theme | Code | Role affinity | Meaning |
| --- | --- | --- | --- |
| 栖息 | `lounge` | psyche / 澄 | 曲面座椅视觉隐喻 |
| 筑台 | `studio` | architecture / 筑间 | 桌面与灯架视觉隐喻 |
| 明径 | `passage` | feng_shui / 青禾 | 拱门与台阶视觉隐喻 |
| 蕨园 | `garden` | biota / 蕨 | 花槽与枝叶视觉隐喻 |
| 回声庭 | `atrium` | soundscape / 汐 | 穹顶与柱列视觉隐喻 |

Council 的 emoji 被可复现的数字 sigil 取代：`01 / 37 / 08 / 22 / 56 / ? / Σ`。它们都标记为“角色视觉隐喻”，不是传感结果。

## Component architecture

- `HomeView.tsx`：后端接线、三信号 rail、置信分离与 truth copy。
- `DigitMorphField.tsx`：单 Canvas、DPR≤2、pointer ref、RAF、reduced-motion、visibility pause。
- `SpatialThemeSelector.tsx`：原生 radio button 语义与五个 Canvas 缩略图。
- `spatial-themes.ts`：五套等点数确定性模板，无 `Math.random()`。
- `PersonaMark.tsx`：各 Agent 的代码原生数字标识。
- `Lenis 1.3.26`：只负责长 Council/Evidence/Story 页面的滚轮插值；不参与实时数据或 Canvas 形变。

## Open-source decision

- Adopt: [Lenis](https://github.com/darkroomengineering/lenis) `1.3.26`, MIT。原生 CSS `scroll-behavior` 不处理滚轮惯性，长审计页需要统一、可停用的滚动生命周期；`respectReducedMotion` 开启，应用设置“减少动态”时 `lerp=1` 且关闭 smooth wheel。
- Do not adopt in core: GSAP（优秀但使用 Webflow/GSAP 自定义许可，不是 OSI 开源；当前单一 Canvas RAF 已足够）、Vanta（Three/WebGL、维护和兼容风险，不解决字符家具核心）、React Bits ASCIIText（Three + 每帧像素读回/DOM 重写，移动端代价高；当前许可证含 Commons Clause）。
- Future option: 页面真正需要复杂滚动章节时才评估 Lenis + timeline；需要纯 OSI 时间线时优先评估 MIT 的 Motion。

## Performance and accessibility gates

- 桌面最多绘制 480 glyph；小于 700px 的 Canvas 使用 stride 2，最多绘制 240 glyph。
- 单 Canvas、pointermove 只写 ref、document hidden 停 RAF、DPR 上限 2。
- 目标 ≥45 FPS，期望 60 FPS；不得降低现有 SignalSculpture perf gate。
- reduced motion 停止自动 morph 与 pointer 形变，主题切换静态重绘。
- 主题使用原生 `button role=radio`、44px 以上点击区、可见 focus；移动端主题目录横向滚动但页面不得横向溢出。
- Canvas 有稳定文字替代，不用 4Hz `aria-live` 轰炸读屏。

## Deliverables

- 设计母版 PNG。
- 1440×900 与 390×844 实际页面截图。
- 5–8 秒实际 Canvas morph GIF，标注 `CONCEPT VISUAL — NOT SENSOR OUTPUT`。
- 五个主题缩略图与七个 Agent sigil（运行时代码原生，不依赖位图）。
- Web unit/type/lint/build、Playwright desktop/mobile、Replay E2E、claim/license/security audit 证据。
