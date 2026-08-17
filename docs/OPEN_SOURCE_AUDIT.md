# GitHub / 开源项目审计

## 1. 结论

不应组合 GitHub 上“所有 WiFi 成像项目”。不同项目依赖的芯片、频段、天线数、驱动、CSI 格式、数据集和许可证并不兼容。主工程只保留一个采集底座：Espressif `esp-csi`。其他项目只能以对照、adapter、算法灵感或研究参考存在。

## 2. 分级

- **A**：允许进入产品主链；锁定 commit、许可证和数据契约。
- **B**：选择性借鉴或隔离 adapter；必须用同一批 ESP32 Replay 做消融，证明增益后才能合并。
- **C**：离线研究；硬件域或许可条件不适合主链。
- **D**：高主张隔离；缺真实数据、匹配权重、硬件拓扑或可复现实验时，不得用于产品能力声明。

## 3. 项目矩阵

| 类别 | 项目 | 硬件/作用 | 许可状态 | 级别 | 处理方式 |
| --- | --- | --- | --- | --- | --- |
| 主采集 | [Espressif ESP-CSI](https://github.com/espressif/esp-csi) | 官方 ESP-IDF CSI；路由器、板间 TX/RX、专用 TX+多 RX | Apache-2.0；仍检查目标文件 SPDX | A | 唯一固件主底座；采用回调、元数据、发送/接收拓扑和官方解析示例 |
| 采集 | [ESP32-CSI-Tool](https://github.com/StevenMHernandez/ESP32-CSI-Tool) | Active AP/STA、Passive、串口/SD CSV；旧 ESP-IDF | MIT | B | 借鉴实验模式、时间戳、录制字段；不整体继承旧工程 |
| 多节点传输 | [ESP32-CSI-Collection-and-Display](https://github.com/Rui-Chun/ESP32-CSI-Collection-and-Display) | 多 ESP32、mDNS/UDP、MAC 过滤、实时显示 | MIT | B | 借鉴节点标识、UDP envelope 和掉线处理；不用旧 UI/简单阈值作为主算法 |
| 信号处理 | [ESPectre](https://github.com/francescopace/espectre) | 单 ESP32+路由器；Hampel、子载波选择、校准 | GPL-3.0 | B | 只做算法消融；非 GPL 产品不得复制代码；不依赖非公开 PHY API |
| 解析 | [csiread](https://github.com/citysu/csiread) | ESP32/Intel/Atheros/Nexmon 多格式 Python/Cython 解析 | MIT | B | 作为解析正确性对照；canonical schema 仍由本项目定义 |
| 处理/可视化 | [CSIKit](https://github.com/Gi-z/CSIKit) | 多格式幅相、滤波与绘图 | MIT | B | 保留研究 adapter；不把它变成实时链唯一依赖 |
| 三节点 Web 壳 | [ESPectre Sense](https://github.com/outputlayer/espectre-sense) | 3×S3、UDP、Rust、WebSocket、Web 热图 | 仓库标示 MIT；锁定 commit 后复核 | B 壳 / C 模型 | 借鉴端到端壳、录制/回放/重标定；模型精度独立复验 |
| 活动识别基准 | [SenseFi](https://github.com/xyanchen/WiFi-CSI-Sensing-Benchmark) | Intel/Atheros 公共集；MLP/CNN/RNN/Transformer | MIT | C | 借鉴 benchmark 和消融；公开准确率不能作为 ESP32 指标 |
| 高带宽采集 | [Nexmon CSI](https://github.com/seemoo-lab/nexmon_csi) | Broadcom/Cypress 固件补丁，20/40/80 MHz | 混合条款，需专项审计 | C | 借鉴 pcap/UDP、子载波处理；不进入 ESP32 固件 |
| 实验室平台 | [PicoScenes](https://ps.zpj.io/) / [Python Toolbox](https://github.com/wifisensing/PicoScenes-Python-Toolbox) | AX200/AX210/QCA9300/IWL5300/SDR | Toolbox MIT；主平台独立许可 | C | 高端实验室对照；不能把主平台称为完全开源或塞入 S3 主链 |
| 传统采集 | [Linux 802.11n CSI Tool](https://github.com/spanev/linux-80211n-csitool) | Intel 5300、多天线、旧驱动 | 混合 GPL/固件条款，需复核 | C | 只借鉴相位清洗、AoA/ToF 研究方法 |
| 传统采集 | [Atheros CSI Tool](https://github.com/xieyaxiongfly/Atheros-CSI-Tool) | ath9k/QCA9300、多天线 | GPL | C | 离线论文参考；不直接用于 ESP32 数据 |
| 3D 姿态 | [Person-in-WiFi 3D](https://github.com/aiotgroup/Person-in-WiFi-3D-repo) | 多链路 Intel 5300、5.64 GHz、CUDA | 代码 Apache-2.0；数据/素材另审 | C | 借鉴置信表达；未按同拓扑重采集重训时不能接入 |
| 生成图像 | [WiFiCam](https://github.com/StrohmayerJ/wificam) | ESP32-S3 CSI + 同步摄像数据，VAE 生成 | 未确认明确软件许可证 | C | 只研究艺术化映射与同步方式；不得复制未授权代码或称真实影像 |
| 深度生成 | [CSI2Depth](https://github.com/Arritmic/csi2depth) | MM-Fi 5 GHz SIMO、Transformer+cGAN、GPU | MIT | C | 借鉴视觉语言；checkpoint 与 2.4 GHz S3 不兼容 |
| 合成数据 | [RF-Diffusion](https://github.com/mobicom24/RF-Diffusion) | PyTorch/GPU 生成复数 RF | GPL-3.0 | C | 后期研究增强；不得代替真机标定或补出空间事实 |
| 高主张系统 | [RuView](https://github.com/ruvnet/RuView) | ESP32 节点、服务、Web；含姿态/生命体征主张 | MIT，但数据/权重/路径逐项审 | D | 可参考 UI/API；先分离 mock、真实 CSI、权重和输出再复验 |

许可信息只是初筛。真正合并前必须在锁定 commit 上执行 SPDX/依赖/数据许可证审计；“GitHub 可见”不等于可复制。

## 4. 引入规则

任何 B/C 项目要进入实验区，必须提交 `OpenSourceCandidate`：

```yaml
repo: https://github.com/...
commit: exact_sha
license: exact_spdx_or_review_required
hardware_domain: ...
input_adapter: ...
expected_gain: ...
baseline_dataset: data/fixtures/frozen_room_v1
metric: ...
acceptance_delta: ...
rollback_plan: ...
```

合并顺序：

1. 锁定 commit 与许可证。
2. 写 adapter，不修改 canonical raw schema。
3. 在同一冻结 Replay 上跑 baseline。
4. 只改变一个模块，跑准确性、延迟、内存和稳定性消融。
5. 增益达到预注册阈值且无许可阻断才合并。
6. 记录失败结果，避免以后重复试验。

## 5. 绝对禁止

- 把 Intel/Nexmon/PicoScenes 数据或准确率描述为 ESP32 真机结果。
- 下载一个公开 checkpoint 后直接输入不同天线数、频段和 CSI 形状。
- 把 RuView、WiFiCam、CSI2Depth 或 Person-in-WiFi 的视觉截图当作本系统传感证据。
- 因为 UI “看起来像人体”就通过验收。
- 未看到许可证时默认 MIT。
- 为了统一项目而保留多套 parser 和多套含义不同的数据字段。

## 6. 主工程可借鉴的能力

开源项目预计能帮助完成采集、解析、基础滤波、录制和可视化壳，约占工程底层能力的一部分。最有价值且必须自建的是：双链路配对、房间标定、三项代理定义、质量门、EvidencePacket、争论协议、Policy Arbiter、置信边界、回放可复现性和多模态体验。

## 7. 前端交互项目审计（2026-08-08）

| 项目 | 审计版本/状态 | 许可证 | 处理 |
| --- | --- | --- | --- |
| [Lenis](https://github.com/darkroomengineering/lenis) | `1.3.26`，活跃 | MIT | **采用**；只服务长审计页滚轮插值，开启 reduced-motion，锁定 npm 版本 |
| [GSAP](https://github.com/greensock/GSAP) | `3.15.0` | Webflow/GSAP Standard License，非 OSI | 首版不采用；Canvas 单一 progress 不足以证明新增自定义许可依赖的必要性 |
| [Vanta](https://github.com/tengbao/vanta) | npm `0.5.24`；发布与默认分支维护信号偏旧 | MIT；另需 Three | 不采用；WebGL/Three 包体、context 与新 Three 兼容风险，且不解决数字家具核心 |
| [React Bits](https://github.com/DavidHDev/react-bits) | 源码复制 registry，不是普通运行时包 | MIT + Commons Clause，非 OSI | 不复制 ASCIIText；其 Three + 像素读回 + DOM 重写不适合实时/移动端；只作交互研究参考 |
| [Motion](https://github.com/motiondivision/motion) | `13.0.0` | MIT | 未来需要纯 OSI 时间线时的候选；本轮不安装 |

新增 `lenis@1.3.26` 的必要性：项目已有 Council、Evidence、Story 等长页；CSS `scroll-behavior` 只覆盖程序化/锚点滚动，不能统一鼠标滚轮惯性和应用内 reduced-motion 生命周期。Lenis 不进入 `StreamState`、Canvas 或音频数据路径，应用设置“减少动态”时使用 `lerp=1` 并关闭 smooth wheel。

本轮没有从 React Bits/Vanta/GSAP 复制源码或素材。代码原生的数字模板和 Agent sigil 均为本项目原创实现。
