# Wire Protocol — ESP32 RX → Host binary frames

Status: **version 1 (draft for Phase 02 host parser + Phase 03 collector)**.

This document is the specification shared by the C encoder
(`firmware/shared/wire_protocol.c`) and the Python reference
(`firmware/shared/python/wire_protocol.py`). The two implementations are
locked byte-for-byte by `tests/firmware_contract/test_golden_c_python.py`.

## 1. General rules

- Byte order is **little-endian** everywhere.
- Every frame is a self-contained binary record: `fixed header | payload |
  crc32`.
- The CRC-32 (IEEE 802.3, zlib-compatible) covers **all bytes before the
  trailing CRC field**; the CRC itself is appended little-endian.
- Frames are delimited by a 4-byte magic, so the host parser can
  resynchronize through arbitrary noise, log lines, or mid-stream corruption.
- Explicit packed serialization only — never a raw, possibly misaligned C
  struct dump.

## 2. Frame header (46 bytes)

| Offset | Size | Field | Type | Meaning |
| --- | --- | --- | --- | --- |
| 0 | 4 | `magic` | u32 | `0x57434652` (`'W','C','F','R'`) |
| 4 | 1 | `version` | u8 | wire protocol version (`1`) |
| 5 | 1 | `frame_type` | u8 | `0x01` data, `0x02` status |
| 6 | 2 | `header_len` | u16 | fixed `46` |
| 8 | 2 | `payload_len` | u16 | payload bytes after header |
| 10 | 4 | `seq` | u32 | TX sequence (data) or status epoch |
| 14 | 8 | `device_ts_us` | u64 | TX timestamp (data) / status send time |
| 22 | 4 | `rx_id` | u32 | synthetic RX board ID (1 = RX-A, 2 = RX-B) |
| 26 | 8 | `tx_id_hash` | u64 | FNV-1a 64 hash of the TX MAC |
| 34 | 1 | `channel` | u8 | 2.4 GHz channel |
| 35 | 1 | `bandwidth_mhz` | u8 | `20` or `40` |
| 36 | 2 | `rssi_dbm_x100` | i16 | RSSI × 100 (e.g. `-6500` = −65.00 dBm) |
| 38 | 2 | `noise_floor_dbm_x100` | i16 | noise floor × 100 |
| 40 | 1 | `phy_flags` | u8 | bitfield, see below |
| 41 | 1 | `first_word_invalid` | u8 | `1` when CSI first word is invalid |
| 42 | 2 | `csi_len` | u16 | CSI bytes in payload (data frames) |
| 44 | 2 | `reserved` | u16 | must be `0` |

`phy_flags` bits:

| Bit | Constant | Meaning |
| --- | --- | --- |
| 0 | `WSC_PHY_FLAG_HT40` | 40 MHz bandwidth |
| 1 | `WSC_PHY_FLAG_SIG_MODE_HT` | 802.11n signal mode |
| 2 | `WSC_PHY_FLAG_STBC` | STBC packet |
| 3 | `WSC_PHY_FLAG_AGGREGATION` | AMPDU aggregation |
| 4 | `WSC_PHY_FLAG_SGI` | short guard interval |
| 5 | `WSC_PHY_FLAG_SMOOTHING` | channel smoothing |
| 6 | `WSC_PHY_FLAG_NOT_SOUNDING` | not-sounding flag |
| 7 | reserved | must be `0` |

## 3. Data frame (`frame_type = 0x01`)

`payload_len == csi_len <= 1024`. CSI bytes follow the header verbatim in the
ESP-IDF order: interleaved signed int8 **imaginary, real** per subcarrier
(see the ESP-IDF Wi-Fi vendor features documentation).

Maximum frame size: `46 + 1024 + 4 = 1074` bytes
(`WSC_FRAME_MAX_LEN`).

## 4. Status frame (`frame_type = 0x02`, 36-byte payload)

| Offset | Size | Field |
| --- | --- | --- |
| 0 | 4 | `uptime_s` |
| 4 | 4 | `free_heap` |
| 8 | 4 | `counter_received` |
| 12 | 4 | `counter_filtered` |
| 16 | 4 | `counter_ring_overflow` |
| 20 | 4 | `counter_serial_drop` |
| 24 | 4 | `counter_bad_length` |
| 28 | 2 | `last_rssi_dbm_x100` |
| 30 | 2 | `last_noise_floor_dbm_x100` |
| 32 | 4 | reserved |

Status frames are emitted once per second. They use the same magic/version/
CRC machinery as data frames, so the host parser never confuses them.

## 5. ESP-NOW TX payload (24 bytes)

| Offset | Size | Field |
| --- | --- | --- |
| 0 | 4 | `magic` `0x58435357` (`'W','S','C','X'`) |
| 4 | 1 | `version` (`1`) |
| 5 | 1 | reserved |
| 6 | 2 | `payload_len` (`24`) |
| 8 | 4 | `tx_id` (synthetic TX board ID) |
| 12 | 4 | `seq` (uint32, wrap defined) |
| 16 | 8 | `tx_ts_us` (esp_timer microsecond clock) |

Receivers parse this payload to obtain the TX sequence and TX timestamp used
for pairing; no real MAC address is transmitted.

## 6. CRC-32

Standard CRC-32: init `0xFFFFFFFF`, polynomial `0xEDB88320`, final xor
`0xFFFFFFFF` (identical to `zlib.crc32`). Known-answer test:
`crc32("123456789") == 0xCBF43926`.

## 7. Sequence and wrap

`seq` is a uint32 that wraps modulo 2^32. The signed gap helper
`wsc_seq_gap(prev, curr)` is defined for `|gap| < 2^31`:

- `gap(0xFFFFFFFF, 2) == 3`
- `gap(2, 0xFFFFFFFF) == -3`

## 8. Host parser resynchronization

The reference parser (`FrameParser`) scans for the magic bytes and then
validates, in order:

1. `version` — unknown versions are rejected (`bad_version`).
2. `header_len == 46` and `frame_type` in {data, status}
   (`bad_type`).
3. `payload_len <= max_csi_len` (`bad_length`).
4. Frame completeness — a truncated frame is buffered until the remaining
   bytes arrive.
5. CRC over `header + payload` — mismatch drops one byte and rescans magic
   (`bad_crc`).

Any non-magic byte before the next frame increments `bad_magic`; the parser
recovers from arbitrary noise. No state survives across sessions.

## 9. Version migration

- **patch** (1.0.x): additive optional fields or clarifications; old readers
  still parse.
- **minor** (1.x): new required behavior ships with an explicit migration
  step; the collector must record the conversion.
- **major** (2.x): incompatible; replay bundles must be converted before use
  and the old format is never silently reinterpreted.

The firmware bakes `WSC_PROTOCOL_VERSION` and `WSC_FW_VERSION` into
`firmware/shared/include/wsc_config.h`.

## 10. Serial transport notes

- Binary frames leave the RX on a dedicated UART (default UART0 at 921600
  baud, TX pin configurable). The RX console is disabled so human-readable
  logs never interleave with the binary stream; diagnostics travel as status
  frames.
- The collector must not assume timing between the two RX devices; TX
  sequence and TX timestamp are the pairing keys.
