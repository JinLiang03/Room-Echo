# 完整实机 Demo BOM

版本：2026-08-08  
适用范围：Wi-Fi CSI 空间感知 Demo（1 个 TX、2 个 RX、三信号代理、Agent Council、Web UI）

## 采购结论

最终 Demo 采用三角形三板拓扑：

- TX ×1：运行 `csi_tx`
- RX-A ×1：运行 `csi_rx`，接主机串口
- RX-B ×1：运行 `csi_rx`，接主机串口

建议采购 **4 套同型号 ESP32-S3 板卡**，其中 3 套工作、1 套备用。严格最低采购量是 3 套，但没有备用板时，现场任何一块板、USB 线或天线故障都会中断演示。

## 主 BOM

| 类别 | 推荐规格 | 最终 Demo 数量 | 说明 |
|---|---|---:|---|
| ESP32-S3 开发板 | **ESP32-S3-DevKitC-1U-N8R8** 同型号同批次；即 ESP32-S3-WROOM-1U、8 MB Flash、8 MB PSRAM、外置天线接口 | 4 | 3 工作 + 1 备用；TX/RX 必须能刷本项目 ESP-IDF 固件 |
| 2.4 GHz 外置天线 | 三块工作板使用相同型号、相同增益、相同接头 | 4 | 3 工作 + 1 备用；不要混用 PCB 天线与外置天线 |
| IPEX/U.FL ↔ SMA 尾线/同轴线 | 与板卡接口匹配，三根工作线长度相同 | 4 | 只有板卡裸露外置天线座时需要；长度不一致会增加校准误差 |
| USB 数据线 | 支持数据传输，不是纯充电线；接口与板卡匹配 | 4 | 3 工作 + 1 备用；RX-A/RX-B 必须直接接主机或稳定的有源 Hub |
| 有源 USB Hub | 带独立供电、至少 4 个数据口 | 1 | 主机 USB 口不足或现场需要统一供电时使用；优先选带独立电源的型号 |
| 固定支架/小三脚架 | 能固定板卡和天线方向 | 3 | TX、RX-A、RX-B 各一个；不要手持测试 |
| 地面胶带/标记贴 | 用于标出三点位置和 5 个深度点 | 1 卷 | 标定和复现实验必需 |
| 卷尺 | 至少 5 m | 1 | 记录板间距离和深度轴位置 |
| Demo 主机 | macOS/Linux 笔记本，至少 3 个稳定 USB 数据口；Python 3.11+、Node 18+ | 1 | 运行 collector、API、Web；当前仓库已提供构建产物和启动脚本 |

## 射频与空间布置要求

这些不是“可有可无的配件”，而是实机 Demo 的验收条件：

1. TX、RX-A、RX-B 必须形成非共线三角形，建议边长 2–4 m，且不小于 1 m。
2. 三块板高度保持 1.1–1.3 m，天线朝向一致并指向空间中心。
3. 从 RX-A 近端到 RX-B 远端标出 5 个深度点；深度代理只能在完成该标定后输出受限结论。
4. 固定 2.4 GHz 信道，优先 HT20；现场先扫描 1/6/11，选择最干净的信道。
5. 关闭 Wi-Fi power-save，使用固定包频率；目标约 100 packets/s，串口默认 921600 baud。

## 软件/固件交付物（不单独采购，但必须准备）

| 交付物 | 数量 | 位置/要求 |
|---|---:|---|
| TX 固件 | 1 | `firmware/build/` 中的 `csi_tx` 构建产物；刷到 TX 板 |
| RX 固件 | 2 | 同一版本 `csi_rx`；分别设置 RX-A=1、RX-B=2 |
| 拓扑文件 | 1 | `hardware/topology.json`；填写板位、方向、距离并生成 `topology_hash` |
| 标定 profile | 1 | 空房、运动、occupancy 三档、5 点 depth 轴和 held-out run；生成 `calibration_profile_id` |
| 串口映射 | 1 | 明确 `TX_PORT`、`RX_PORTS=rx-a=...,rx-b=...`，禁止自动猜测角色 |

## 两个采购档位

### 推荐档：现场可完成最终 Demo

```text
ESP32-S3 同型号板       4
2.4 GHz 外置天线         4
匹配 IPEX/U.FL 尾线      4（板卡需要时）
USB 数据线               4
有源 USB Hub             1
固定支架/三脚架           3
地面胶带                 1
5 m 卷尺                 1
```

### 最低档：只能做受限实机验证

```text
ESP32-S3 同型号板       2（TX + RX）
2.4 GHz 外置天线         2
USB 数据线               2
主机                     1
```

最低档可以验证 CSI 获取、运动强度和链路健康，但 **不能作为完整 Demo**：只有一个 RX 时，`depth_zone_proxy` 应保持 unknown/低置信度，不能宣称完成三信号空间感知。

## CAPSO 测试板的复用规则

- 如果 CAPSO 板确实是 ESP32-S3，并且有兼容的 2.4 GHz 天线接口和 USB 串口，可以先作为 TX 或 RX 做采集冒烟测试。
- 不需要修改 CAPSO 项目源码；但刷本项目固件前必须确认板卡引脚、USB-UART、天线开关和供电方式与本项目匹配。
- 最终三板 Demo 建议使用同型号、同批次板卡。CAPSO 板与另一种板卡混用时，必须重新做空房/运动/occupancy/depth 标定，不能直接复用旧 profile。

## 当前状态与验收边界

当前仓库的 Replay Demo 可运行，但 `hardware/hardware_inventory.json` 仍为 `blocked_by_hardware`：尚未确认三块 ESP32-S3、天线、板位和 5 点深度轴。因此以上 BOM 是“完成实机 Demo 的采购目标”，不是硬件已经通过的证明。

硬件到齐后，按 `docs/LIVE_SETUP.md` 依次执行 hardware sanity、live 启动、标定和 held-out 测试；在这些门通过前，页面中的推断必须继续标为 inference/unknown，不能当作摄像头等价图像或真实人体识别。
