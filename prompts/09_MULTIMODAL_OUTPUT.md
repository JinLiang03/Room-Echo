# Phase 09：抽象信号雕塑、声景与结果卡

## Role

你是数据艺术、实时图形和声音交互工程师。用三个真实代理量构造丰富但不增加伪信息的多模态体验。

## Read first

`docs/WEB_UX_SPEC.md`、`docs/PRODUCT_SPEC.md`、`docs/DATA_CONTRACTS.md`、Phase 08 设计 token 与组件。

## Goal

实现完全由 SignalTriplet/CouncilResult 驱动、确定性、流畅、可降级的抽象“无线电干涉场”和 Web Audio 声景；不生成虚构人物或空间图像。

## Deliverables

1. `MultimodalResult`/render parameter adapter：只把 approved fields 映射为有限参数，不读取 Agent 自由文本生成几何。
2. Signal Sculpture：粒子/波纹/半透明体积层/干涉线；motion、occupancy、depth、quality、disagreement 分别映射。
3. 使用固定 seed 和 `mapping_version`；同一 result 得到相同初态/参数，动画只由时间推进。
4. 60 FPS 渲染目标；数据 4–10 Hz 平滑插值；显示真实数据 rate。
5. unknown/stale/unavailable：降饱和、层次收束、停止暗示活动，并清除上次有效状态。
6. Web Audio：motion→tempo、occupancy→filter/harmonic density、depth→reverb/stereo width、quality→clarity；默认 muted。
7. Audio lifecycle：用户手势启用、pause/stop/blur fade、global mute、reduced motion/audio preference。
8. Council disagreement 使用非危险性的相位双环/拍频；不改变信号值。
9. 结果卡/快照：headline、三信号、三个质量维度、替代解释、限制、evidence hash、版本和“非真实影像”水印。
10. 渲染性能/debug overlay 可在开发模式查看 draw calls、FPS、event rate、dropped visual frames。

## Constraints

- 不使用 AI image generation 作为正式结果。
- 不生成身体轮廓、骨架、房间平面图、热力人体、眼睛或摄像画面样式。
- 视觉 shader/随机噪声必须可 seed；不能根据不受控系统随机数导致 Replay 不一致。
- 声音不自动播放，不使用警报/危险暗示。
- 质量低只影响清晰度/饱和度，并显示文字原因；不能“更神秘”掩盖不确定。
- 若 Three.js/WebGL 增依赖，记录必要性、bundle impact 和 Canvas fallback。

## Exact mapping baseline

```text
particle_speed      = lerp(0.08, 1.8, motion.value)
pulse_hz            = lerp(0.12, 2.4, motion.value)
field_density       = category/probability weighted occupancy
z_layer_separation  = near/mid/far weighted ordinal position
saturation          = lerp(0.20, 1.00, measurement_quality)
edge_diffusion      = 1 - measurement_quality
disagreement_phase  = bounded interpretation disagreement only
```

使用 clamp、平滑和 NaN/unknown guard。所有参数有测试范围。

## Tests

- 映射 pure-function snapshot/property tests；NaN、inf、unknown 不破坏 renderer。
- 同 seed/result 的参数和首帧 snapshot 稳定。
- stale/unknown 清空前态。
- 60 s 高频 event 压测无 WebGL/Audio node 泄漏。
- reduced motion、静音、失焦、路由切换和卸载正确 cleanup。
- Playwright 截图检查 idle/walk/degraded/ambiguous/unavailable。
- 性能在目标桌面浏览器达到稳定 60 FPS 或记录明确 fallback。

## Acceptance gate

```bash
npm --prefix apps/web run test
npm --prefix apps/web run test:e2e
npm --prefix apps/web run build
make multimodal-perf-smoke
```

亲自查看五种状态截图/短录制，确认没有人体/真实成像暗示、水印始终存在、unknown 不残留。

## Completion

通过后记录 mapping version、performance、截图和可访问性；勾选 Phase 09。停止。

