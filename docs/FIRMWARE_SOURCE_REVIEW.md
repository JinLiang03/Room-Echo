# Firmware source review — esp-csi and ESP-IDF CSI docs

Date: 2026-08-06. Network review performed before writing Phase 02 firmware.

## Sources reviewed

1. Espressif **esp-csi** repository, commit
   `8633d67152db2808f141cc1595970aa9cf406045`
   (current `master` HEAD at review time):
   <https://github.com/espressif/esp-csi>
   - `examples/get-started/csi_send/main/app_main.c`
   - `examples/get-started/csi_recv/main/app_main.c`
   - `examples/get-started/tools/csi_data_read_parse.py`
   - `examples/get-started/{csi_send,csi_recv}/sdkconfig.defaults`
   - `examples/get-started/{csi_send,csi_recv}/main/idf_component.yml`
2. ESP-IDF stable documentation, “Wi-Fi Vendor Features” (CSI section):
   <https://docs.espressif.com/projects/esp-idf/en/stable/esp32/api-guides/wifi-driver/wifi-vendor-features.html>

## Key facts recorded

- The CSI callback runs on the Wi-Fi task; the docs explicitly require
  delegating work to a lower-priority task and never doing lengthy operations
  in the callback. This project's RX callback only filters, packs, and
  enqueues.
- Each subcarrier is two signed bytes: **imaginary first, real second**;
  `first_word_invalid` means the first four CSI bytes are invalid.
- `wifi_csi_info_t` provides `buf`, `len`, `mac`, `rx_ctrl` (rssi, rate,
  noise_floor, channel, timestamp, …), `first_word_invalid`, and the ESP-NOW
  `payload`/`payload_len` for data packets.
- HT20/HT40 CSI byte counts follow the ESP-IDF table (LLTF/HT-LTF/STBC-HT-LTF);
  this project pins HT20 and allows up to 1024 CSI bytes per frame.
- The get-started examples print CSV from inside the callback — explicitly
  **not** followed here (binary frames, serializer task).
- The example pins ESP-IDF 5.5.0 and uses `esp_csi_gain_ctrl` for gain
  compensation. This project pins `idf: ">=5.5.0,<6"` and defers gain
  compensation to the calibration phase.
- The example sets both devices' STA MAC to the configured TX MAC; the RX
  firmware follows the same pattern for peer filtering.

## Pinned versions

- ESP-IDF: `>=5.5.0,<6` (recorded in both `idf_component.yml` files).
- esp-csi: commit `8633d67152db2808f141cc1595970aa9cf406045` (recorded in the
  build manifest by `scripts/build_firmware.sh`).
- Target: ESP32-S3 by default (toolchain target configurable in
  `scripts/build_firmware.sh`).

## License and provenance

The reviewed example is Apache-2.0 / CC0. Our firmware is original code
informed by the example's structure; it is Apache-2.0 and does not copy the
example's CSV callback or hardcoded channel constants.
