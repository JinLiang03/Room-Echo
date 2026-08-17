# Phase 08：实时 Web 体验、证据与争论界面

## Role

你是交互与前端工程师。把复杂系统变成两分钟能看懂、长时间能调试的 Web 体验。此阶段先完成信息、状态和实时性能；抽象视觉/声音的精细实现留到 Phase 09。

## Read first

`docs/WEB_UX_SPEC.md`、`docs/PRODUCT_SPEC.md`、`docs/DATA_CONTRACTS.md`、`docs/AGENT_COUNCIL.md`、现有 API/WS contracts。

## Goal

实现 Observe、Council、Evidence、Replay 四类体验，严格区分测量、模型、推理和生成层，并在断线/未知/降级时诚实显示。

## Deliverables

1. App shell、路由、ErrorBoundary、Session store、WebSocket client、sequence/reconnect/snapshot 恢复。
2. 顶栏：source mode、Session、TX/RX、channel/bandwidth、calibration、freshness、Start/Pause/Stop/Record。
3. Observe：三张信号卡、当前 supported/ambiguous/unavailable、首要替代解释、限制、场景 placeholder。
4. Council：按周期/阶段显示 claim、evidence chip、challenge、response/revision/concession、policy rejection、final。
5. Evidence：三信号曲线、raw/filter/threshold/unknown 区段、packet/pairing/interference/OOD/calibration、topology、provenance。
6. Replay：bundle list/verify、play/pause/step/seek/speed、markers、recompute 状态、ground truth 默认隐藏。
7. measured/inferred/generated/simulated 永久图例；首屏显示非真实影像水印。
8. 设置：静音、减少动态、颜色/对比、调试信息、数据导出。
9. 1440×900 和 390×844 响应式布局；键盘、ARIA、焦点和色弱安全。
10. Story/demo route，可用 Mock/Replay 固定状态快速检查所有视觉状态。

## State behavior

- `unknown/unavailable` 不显示上次有效值或残影。
- stale overlay 明确，恢复前不假装实时。
- measurement quality、model support、interpretation agreement 三者并列，绝不混合。
- 图表显示真实数据刷新率；UI 插值与 60 FPS 不能冒充传感帧率。
- 无 Agent 时三信号持续；Council 显示“讨论不可用”而不是 loading forever。
- out-of-order WS event 丢弃并统计；重连从 last sequence 恢复。

## Design system

从 CSS tokens 开始：深黑/冷白、亮蓝、紫罗兰、青绿少量；状态色独立。字体、间距、圆角、阴影、运动时间均 token 化。不要使用俗套机器人头像、霓虹网格、人体轮廓、虚构热图或密集 dashboard 拼盘。

## Tests

- Store/reducer 对所有 event type、out-of-order、snapshot/reconnect。
- 三信号卡的 valid/degraded/unknown/stale。
- Council 无 ref/rejected/ambiguous/timeout。
- Replay checksum failure 和 ground truth hidden。
- Accessibility audit、keyboard navigation、reduced motion。
- Playwright desktop/mobile screenshots；检查 clipping、overflow、z-index、加载/错误态。
- 长列表/高频 WS 下无明显 re-render 风暴；记录性能。

## Acceptance gate

```bash
npm --prefix apps/web run lint
npm --prefix apps/web run typecheck
npm --prefix apps/web run test
npm --prefix apps/web run build
npm --prefix apps/web run test:e2e
```

启动 Replay API + Web，手工检查固定演示路线。保存 desktop/mobile screenshot artifact 并真正查看，不只检查文件存在。

## Completion

通过后在 State 记录截图、E2E 和已知 UX 问题；勾选 Phase 08。停止，不实现 Phase 09 高级场与声音。

