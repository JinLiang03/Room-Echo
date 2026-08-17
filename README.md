# WiFi Spatial Council：完整 Codex 开发提示词工程

这是一个面向 `ESP32 Wi-Fi CSI + 多 Agent 协商 + Web 多模态演示` 的逐阶段开发工程包。将本目录作为项目根目录交给 Codex，按 `RUN_ORDER.md` 依次执行提示词，最终目标是得到一个同时支持真机和录制回放的可运行 Demo。

## 最终交付目标

系统从两条独立 CSI 链路中实时计算三个可解释的派生量：

1. `motion_intensity`：活动强度，范围 0–1。
2. `occupancy_density_proxy`：空间占用/遮挡密度代理，输出低/中/高概率。
3. `depth_zone_proxy`：传播纵深/距离变化代理，输出近/中/远/未知概率。

随后由信号质检、活动、空间、纵深、怀疑者和主持人等 Agent 进行独立分析、质疑、修订与综合，Web 端同步呈现：

- 三个实时数据、原始链路健康度和置信度；
- Agent 观点、反证、争议点和最终综合；
- 基于数据驱动的动态空间场、色彩、粒子和 Web Audio 声景；
- Live、Replay、Mock 三种模式及可复现的演示脚本。

## 重要能力边界

这不是摄像机，也不能承诺“完美透视成像”。ESP32 CSI 能感知无线信道变化，但三个输出都是经过环境标定后的统计代理量：

- 多 Agent 一致只能提高“解释一致度”，不能提高传感器本身的置信度。
- `final_claim_confidence` 必须受 `sensor_confidence` 上限约束。
- 未达到验收阈值时，界面必须显示 `unknown / insufficient_signal`，禁止补猜。
- Web 中的场景是“推断场”，必须永久显示 `INFERENCE FIELD — NOT A CAMERA IMAGE`。
- 任何跨房间、穿墙、人数、身份、姿态、精确距离的主张，都不属于 MVP 验收范围。

## 推荐硬件拓扑

稳定演示使用三块支持 CSI 的 Espressif 开发板：

- 1 × 专用发送端 TX；
- 2 × 非共线布置的接收端 RX-A / RX-B；
- 主机通过两条 USB 串口接收数据。

两块板的一发一收可以先跑通，但 `depth_zone_proxy` 只能作为低置信度输出。若只用路由器加一块板，也能采集，但可复现性和空间分辨能力更弱。

## 工程完成后的目标目录

```text
wifi-spatial-council/
├── AGENTS.md
├── PROJECT_INDEX.yaml
├── STATE.md
├── TASKS.md
├── firmware/
│   ├── csi_tx/
│   ├── csi_rx/
│   └── shared/
├── services/
│   ├── collector/
│   ├── sensing/
│   ├── council/
│   └── api/
├── apps/
│   └── web/
├── packages/
│   └── contracts/
├── data/
│   ├── fixtures/
│   ├── calibration/
│   ├── raw/
│   └── derived/
├── configs/
├── scripts/
├── tests/
├── docs/
└── prompts/
```

## 两条互不阻塞的运行路径

| 路径 | 数据源 | 是否需要 ESP32 | 用途 |
| --- | --- | --- | --- |
| Replay / Mock | 固定录制样本或确定性合成器 | 否 | 第一周就完成全链路和 Web 演示 |
| Live | TX + RX-A + RX-B | 是 | 标定、真机验收与最终演示 |

Replay 与 Live 必须实现同一个 `FrameSource` 接口。硬件未接好时，不允许上层开发停摆；真机接好后，也不允许重写 Web 或 Agent 层。

## 推荐技术栈

- Firmware：ESP-IDF；主链基于 Espressif `esp-csi`。
- Host：Python 3.11+、FastAPI、Pydantic v2、NumPy、SciPy、Polars/PyArrow。
- Agent：OpenAI Agents SDK for Python，Pydantic 结构化输出；提供 `mock` provider。
- Web：React、TypeScript、Vite、Zustand、TanStack Query、WebSocket、Canvas/WebGL、Web Audio API。
- 测试：pytest、Hypothesis、Vitest、Playwright；硬件测试单独打 `hardware` marker。

## 快速开始

1. 阅读 `RUN_ORDER.md`。
2. 在 Codex 中先执行 `prompts/01_BOOTSTRAP.md`。
3. 每一阶段验收通过后再执行下一份提示词。
4. ESP32 未到位时一直使用 Replay 模式；到位后执行第 11 阶段。
5. 最终运行 `uv run python scripts/verify_release.py` 和端到端测试，验收结果写入 `STATE.md`。

也可以把 `prompts/00_MASTER_BUILD.md` 一次性给 Codex，让它按阶段连续执行；但仍必须逐门验收，不能跳过失败项。

## 验收结果不是预先保证

工程中列出的帧率、准确率、延迟和稳定性是“通过门槛”，不是预先宣称已经达到。真实结果取决于天线、房间、板卡、干扰、布置、采样和标定。任何达不到的指标必须以失败报告和降级行为结束，而不是修改测试来制造通过。

## 核心来源

- Espressif ESP-CSI 主仓库：<https://github.com/espressif/esp-csi>
- ESP-IDF Wi-Fi CSI 格式：<https://docs.espressif.com/projects/esp-idf/en/stable/esp32/api-guides/wifi-driver/wifi-vendor-features.html>
- ESP-CSI get-started：<https://github.com/espressif/esp-csi/tree/master/examples/get-started>
- OpenAI Agents SDK：<https://developers.openai.com/api/docs/guides/agents>
- OpenAI Structured Outputs：<https://developers.openai.com/api/docs/guides/structured-outputs>
- Codex 最佳实践：<https://learn.chatgpt.com/guides/best-practices>
