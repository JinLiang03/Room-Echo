# Phase 02：ESP32 TX/RX 固件与二进制帧

## Role

你是 ESP-IDF 与实时嵌入式工程师。以 Espressif `esp-csi` 为唯一采集主链，建立可编译、可观测、不会在 CSI callback 内阻塞的 TX/RX 固件。

## Read first

`docs/HARDWARE_AND_CALIBRATION.md`、`docs/DATA_CONTRACTS.md`、`docs/OPEN_SOURCE_AUDIT.md`，以及 Phase 01 生成的 contracts 与 ADR。

## Required source review

在联网可用时阅读并记录所用 commit：

- <https://github.com/espressif/esp-csi>
- `examples/get-started/csi_send`、`csi_recv`、`tools`
- <https://docs.espressif.com/projects/esp-idf/en/stable/esp32/api-guides/wifi-driver/wifi-vendor-features.html>

不要从 B/C/D 级仓库复制固件主链。

## Goal

实现专用 TX 发包与两个同固件 RX 接收；RX 把 canonical 必需字段包装成带 magic/version/length/CRC 的二进制串口帧，主机能可靠 resync。

## Deliverables

1. `firmware/csi_tx`：固定 target、信道、HT20、无 power save；100 packet/s 可配置；payload 含 protocol version、TX ID、`uint32 seq`、TX timestamp。
2. `firmware/csi_rx`：只接收配置 TX MAC/ID；启用 CSI；读取 rx_ctrl、CSI bytes 和 invalid flag。
3. `firmware/shared`：wire protocol、CRC、config、build/version 信息。
4. RX callback：预分配 pool/ring buffer；仅复制+enqueue；满时计数并丢该帧，绝不阻塞。
5. Serializer task：二进制输出；状态/日志与数据帧分离，避免 parser 混淆。
6. 运行时 counters：received、filtered、ring_overflow、serial_drop、bad_length、uptime、free heap；每秒低频状态帧。
7. `sdkconfig.defaults` 和 board config 示例；SSID/MAC/信道不写死在源码。
8. 协议文档 `docs/WIRE_PROTOCOL.md`：字节序、字段表、最大长度、CRC、resync、版本迁移。
9. Python reference encoder/decoder fixture，与 C 结构 golden bytes 对齐。
10. `scripts/build_firmware.sh` 或 Make target；生成 build manifest，记录 ESP-IDF tag 与 esp-csi commit。

## Wire protocol minimum

```text
magic | version | frame_type | header_len | payload_len | seq | device_ts_us
rx_id | tx_id_hash | channel | bandwidth | rssi | noise_floor | PHY flags
csi_len | first_word_invalid | csi_bytes | crc32
```

使用明确 packed/serialization 实现，不允许直接 dump 未对齐 C struct。检查长度上限和整数溢出。

## Constraints

- 不在 callback 中 printf/CSV/FFT/JSON/heap allocate/串口 write。
- 不假设两块 RX 时钟或相位同步。
- 不实现 AoA、TDoA、ToF、人物/人数/姿态。
- 不把真实 MAC 写入公开 fixture；hash/synthetic ID。
- 不自动 flash。此阶段只 build 和 host parser test。

## Tests

- C/Python golden frame 编解码相同。
- CRC 错、截断、oversize、noise bytes、未知版本、错误 magic 能 resync/拒绝。
- seq wrap-around 有定义。
- ring overflow 不死锁并有 counter。
- TX/RX 两个 target 均干净 build。
- 编译警告按项目策略视为错误；静态检查关键内存路径。

## Acceptance gate

```bash
make firmware-build
python -m pytest tests/firmware_contract
python -m ruff check firmware services packages tests
```

保存 build manifest 和大小报告。若 ESP-IDF 不可用，不能标记通过；记录 exact blocker。禁止伪造 build output。

## Completion

通过后更新 State/Tasks，写明“built, not flashed/not hardware validated”。停止，不执行 Phase 03。

