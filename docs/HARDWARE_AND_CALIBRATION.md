# 硬件、采集与标定

## 1. 推荐 BOM

- 3 × 同型号、支持 ESP-IDF CSI 的开发板；推荐使用带外置天线接口的同批次 ESP32-S3 开发板。
- 3 × 同型号 2.4 GHz 外置天线及相同长度馈线。
- 3 × 稳定独立 USB 供电/数据线；RX-A/RX-B 直连主机 USB。
- 地面定位胶带、卷尺、三脚架或固定支架。
- 可选：独立 2.4 GHz 频谱/信道扫描设备，用于现场选信道。

Espressif 的 get-started 文档建议外置天线，并要求收发设备距离大于 1 m；官方总览把“专用发包设备 + 多接收端”列为高准确性/可靠性方式。参考：<https://github.com/espressif/esp-csi> 和 <https://github.com/espressif/esp-csi/blob/master/examples/get-started/README.md>。

## 2. 布置

- TX、RX-A、RX-B 放在目标区域三个顶点，绝不共线。
- 高度保持 1.1–1.3 m；两两距离建议 2–4 m，最低大于 1 m。
- 三根天线方向一致并朝向目标区域中心；固定后贴防移动标记。
- 预先定义一条从 RX-A 近端指向 RX-B 远端的 depth axis，并标 5 个点。
- 家具、门窗、空调、人员路径必须记录；演示与标定保持一致。

## 3. 射频配置

- 固定 2.4 GHz 信道。部署前扫描 1/6/11，选择干扰最低者。
- 优先 HT20 稳定模式；只有现场证明 HT40 干净且一致时才使用 HT40。
- 关闭 Wi-Fi power save，固定发包节奏。
- 目标 100 packet/s；每包携带递增 `uint32 seq`，RX 用源 MAC 过滤。
- 每个 RX 通过独立 USB-UART 发送二进制帧，建议 921600 baud 或验证后的更高速率。
- 固定 ESP-IDF tag、ESP-CSI commit、sdkconfig 和板卡 target；禁止长期跟随 `master`。

## 4. Firmware 规则

ESP-IDF 文档说明 CSI 是子载波信道频率响应，每个复数值以两个有符号字节记录，顺序为 imaginary、real：<https://docs.espressif.com/projects/esp-idf/en/stable/esp32/api-guides/wifi-driver/wifi-vendor-features.html>。

CSI 回调运行在 Wi-Fi task，因此回调只能：

1. 校验空指针和基本长度。
2. 复制固定上限字段与 CSI bytes 到预分配 ring buffer。
3. 增加 drop/overflow counter。
4. 立即返回。

解析、序列化、串口写入、CSV、FFT、日志和模型全部在其他任务中完成。包中保留：`seq`、device timestamp、TX hash、channel、bandwidth、RSSI、noise floor、PHY metadata、CSI length、first_word_invalid、CSI bytes、CRC。

## 5. 清洗规则

每个 RX 独立执行：

1. 丢弃错误 TX、错误信道、长度/PHY/带宽突变、CRC 错误的包。
2. 若 `first_word_invalid=true`，按 ESP-IDF 说明剔除无效开头数据。
3. 统一 LTF 段和子载波索引，排除 DC、guard 与不适用位置。
4. 将 interleaved IQ 转为复数；幅度计算为 `20 log10(sqrt(I²+Q²)+ε)`。
5. 用前 30 秒检查增益稳定；完整空场 120 秒建立每链路/子载波中位数与 MAD。
6. 按空场方差淘汰最不稳定 20% 子载波；剩余少于 32 个时该链路 invalid。
7. 对帧内公共模态进行鲁棒去除，再计算时间差分和频域特征。

不同 ESP32 接收机没有可依赖的跨设备载波相位同步。MVP 只使用幅度和单链路形状变化，不实现跨 RX 原始相位差。

## 6. 现场标定协议

每个场地、每次拓扑变化都必须执行：

1. **预热**：上电后 30 秒，确认信道、带宽、发包率和 RX 过滤。
2. **空场**：门窗、空调、家具保持正式演示状态，采 120 秒。
3. **标准运动**：一人按固定路径匀速行走 30 秒 × 3 轮，确定 motion 量程。
4. **空间占用代理**：随机顺序采集 low/medium/high 三种扰动覆盖状态，每种 60 秒 × 3 轮；标签是场景等级，不是人数。
5. **纵深**：沿预设轴 5 个地面点，每点 20 秒 × 3 轮，拟合近/中/远分区或单调映射。
6. **留出**：额外随机采集至少一轮，不能参与拟合，只用于验收。
7. **记录**：房间 ID、板卡 ID/hash、精确位置、天线方向、信道、带宽、固件 hash、时间、环境备注。
8. **签名**：生成 `topology_hash`、`calibration_profile_id` 和校验和。

## 7. 标定失效条件

以下任一发生，必须让 occupancy/depth 进入 `uncalibrated` 或重新标定：

- 更换板卡、天线、馈线或 USB 供电；
- TX/RX 移位超过记录容差或改变天线方向；
- 改信道、带宽、固件、特征或估计器版本；
- 大型家具、墙体、门窗常态或空调状态改变；
- 次日快速复测显示指标下降超过阈值。

## 8. 硬件降级

| 情况 | 行为 |
| --- | --- |
| RX-A 或 RX-B 掉线 | 保留单链路 motion；depth 立即 unknown；occupancy 视模型依赖降级或 unknown |
| TX 消失 | 两个窗口内 stale，停止推断 |
| 发包率不足/持续丢包 | degraded 或 invalid，不插值补真值 |
| topology hash 不匹配 | occupancy/depth unavailable |
| 信道切换或 PHY 长度突变 | 终止当前 Session，要求新标定 |
| 强干扰/OOD | 显示干扰警告，冻结或拒绝结果 |

## 9. 可替代硬件

一发一收两块板可用于 Phase 02–04 和 motion 演示；路由器 + 1 RX 可用于快速采集。但只有推荐的三板非共线拓扑才进入 depth 的正式验收。后续若迁移 ESP32-C5/C6 或高带宽 Intel/Nexmon/PicoScenes，必须创建新的 adapter、数据域和标定，不得与 S3 指标混用。

