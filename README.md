# 空间回声 Room Echo


> 一份不用摄像头的空间日记：让多个 Agent 把 Wi-Fi 的微小变化转译成可感知、可质疑、可保存的房间回声。

空间回声是一个隐私优先的 Personal Agent 原型，技术底座名为 **WiFi Spatial Council**。它面向不愿被摄像头持续记录、但希望感知和回看小型空间节奏的独立创作者。系统将 Wi-Fi CSI 的变化转换为三个经过质量门控的代理信号，再由五个解释 Agent、一个怀疑者和一个综合者围绕同一份封存证据提出解释、反证与受限结论。

公开体验使用明确标注的 **Replay** 数据。它不是摄像成像，不识别身份、人数、姿态或行为，也不提供精确距离。

## 核心体验

1. **此刻**：彩色数字场随活动、遮挡/空间占用和相对纵深代理变化。
2. **保存**：点击或长按画面，把这一刻保存为仅存于当前浏览器的视觉书签。
3. **记忆**：回看已保存的空间时刻，并重新播放对应的代理信号状态。
4. **为什么**：查看多个 Agent 的提案、怀疑、修订、拒绝和最终受限结论。
5. **主动未知**：证据或标定不足时，系统明确输出 `unknown / insufficient_signal`，不会补猜。

##三分钟Replay启动

要求：Python 3.11–3.13、[uv](https://docs.astral.sh/uv/)、Node.js 20+。

```bash
make setup
make demo MODE=replay SCENARIO=demo_2min
```

打开 <http://127.0.0.1:5173/#/home>。该命令启动 FastAPI、WebSocket 和 Vite 开发服务器；不需要 ESP32，也不需要模型密钥。确定性 Mock Provider 只用于可复现的离线评测。

比赛提交的单域生产启动、Docker 和公网部署方式见 [SUBMISSION_README.md](SUBMISSION_README.md)；运营与故障排查见 [README-OPERATOR.md](README-OPERATOR.md)。

##Agent如何参与核心流程

```text
Replay / Mock / Live FrameSource
          ↓
清洗、配对、环境基线与质量门
          ↓
活动强度 / 遮挡与空间占用代理 / 相对纵深代理
          ↓
封存 EvidencePacket（Agent 不读取原始 CSI）
          ↓
5 个解释 Agent → 怀疑者交叉质询 → Policy → 综合 Agent
          ↓
受 sensor_confidence_cap 约束的结果、审计记录、Web 体验
```

UI 流不会等待模型调用。五个解释 Agent 首轮有界并发，安全观点、质疑和回应会逐步显示；流约每 7 秒提供一份最新封存快照，角色会基于上一轮观点说明“保持、增强、减弱或转变”。Agent 只读取带版本、来源、质量字段和完整性哈希的紧凑 `EvidencePacket`，不读取原始 CSI 数组。每个结论都保留证据引用、反证、模型与延迟记录；`final_claim_confidence <= sensor_confidence_cap` 由代码和测试共同约束。

数字场仍只由四项确定性输入驱动：活动控制速度/振幅，占用代理控制聚散/密度，相对纵深控制前后层次，质量控制清晰/破碎。Agent 只能叠加角色颜色与响应效果，不能回写或改变任何底层测量结果。

真实模型密钥只放在服务器环境变量中。常规运行支持
`AGENT_PROVIDER=openai|deepseek`；比赛公网的连续 Replay 则保持确定性 Mock，另由
`POST /api/agent/invoke`（以及 MCP `invoke_room_echo`）对一份已封存证据执行
一次完整、缓存且有调用记录的真实 Council。没有凭据时接口明确返回
`503`，不得把 Mock 输出描述成在线大模型结果。真实调用证明只统计
`status=ok` 的模型请求，缓存命中不计入 `real_model_calls`。

当前公网版本已在 Render 提交 `845f117` 上完成一次真实 DeepSeek Council：
`provider=deepseek`、`model=deepseek-v4-flash`、10 次真实调用，覆盖
propose / cross-examine / respond / synthesize；脱敏调用记录位于
`artifacts/submission/deepseek-full-council-evidence.json`。连续 Replay 仍保持
Mock，因此不会因循环播放持续消耗模型额度。

## 数据源与当前状态

| 模式 | 数据源 | 硬件 | 当前用途 |
|---|---|---:|---|
| Replay | 校验过的录制 bundle | 不需要 | 提交体验、自动测试、可复现演示 |
| Mock | 确定性场景生成器 | 不需要 | 故障、边界和离线开发 |
| Live | 1 × TX + 2 × RX ESP32 | 需要 | 现场采集与标定 |

Replay 端到端闭环可运行。Live 源码和串口协议已存在，但三块 ESP32 的现场标定、held-out 验收和 Live-vs-Replay 证据仍是硬件阻塞项；在这些门禁真实通过前，不能声称 Live 已完成。

## 重要能力边界

- `motion_intensity` 是活动强度代理，范围 0–1。
- `occupancy_density_proxy` 是相对空场基线的遮挡/空间占用代理。
- `depth_zone_proxy` 是沿已标定轴的近/中/远相对纵深代理，不是米制深度。
- Agent 一致度与传感器置信度始终分离；多个 Agent 同意不会提高传感器本身的置信度。
- 视觉永久作为 **INFERENCE FIELD — NOT A CAMERA IMAGE**，不是现场图像。
- 跨房间、穿墙、人数、身份、姿态、情绪、危险判断和精确距离均不在能力范围。

更完整的隐私与限制说明见 [docs/PRIVACY.md](docs/PRIVACY.md) 和 [docs/LIMITATIONS.md](docs/LIMITATIONS.md)。

## 验证

```bash
python -m ruff check .
python -m mypy services packages
python -m pytest -m "not hardware"
npm --prefix apps/web run lint
npm --prefix apps/web run typecheck
npm --prefix apps/web run test
npm --prefix apps/web run build
make e2e-replay
```

硬件测试单独标记为 `hardware`，不会在 Replay 门禁中伪装成通过。发布状态和已知阻塞记录在 [STATE.md](STATE.md)；体系结构入口见 [PROJECT_INDEX.yaml](PROJECT_INDEX.yaml)。

## 项目结构

```text
firmware/            ESP-IDF TX/RX 与版本化串口协议
services/collector/  Mock、Replay、Live 数据源与 append-only 采集
services/sensing/    清洗、标定、三项代理信号与 Evidence 构建
services/council/    Agent Provider、编排、质询、Policy、审计
services/api/        FastAPI、Replay 控制、WebSocket 恢复
apps/web/            React + TypeScript + Vite 体验
packages/contracts/  Pydantic 合约、JSON Schema、生成 TS 类型
data/fixtures/       冻结 Replay 与合约 fixtures
tests/               Python、Vitest、Playwright 与故障测试
submission/          比赛文案、真实用户验证表和提交清单
```

## 协作开发

请从主分支创建 `codex/<topic>` 或 `feature/<topic>` 分支，通过 Pull Request 合并；不要把 `.env`、密钥、真实人物资料、串口设备路径、`.venv`、`node_modules` 或生成的测试产物提交到 Git。完整协作约定见 [docs/CONTRIBUTING.md](docs/CONTRIBUTING.md)。

## 主要技术来源

- [Espressif ESP-CSI](https://github.com/espressif/esp-csi)
- [ESP-IDF Wi-Fi CSI 文档](https://docs.espressif.com/projects/esp-idf/en/stable/esp32/api-guides/wifi-driver/wifi-vendor-features.html)
- [OpenAI Agents SDK](https://developers.openai.com/api/docs/guides/agents)
- [DeepSeek API 文档](https://api-docs.deepseek.com/)
