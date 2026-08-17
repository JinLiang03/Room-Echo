/*
 * WiFi Spatial Council — binary wire protocol between ESP32 RX and the host.
 *
 * Byte order is little-endian everywhere. Frames are magic-delimited so the
 * host can resynchronize through arbitrary noise bytes. CRC-32 covers the
 * whole frame except the trailing CRC field.
 *
 * SPDX-License-Identifier: Apache-2.0
 */
#ifndef WSC_WIRE_PROTOCOL_H
#define WSC_WIRE_PROTOCOL_H

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

#include "wsc_config.h"

#ifdef __cplusplus
extern "C" {
#endif

/* Data frame header (46 bytes, little-endian). */
#define WSC_MAGIC_U32        0x57434652u /* 'W','C','F','R' */
#define WSC_FRAME_TYPE_DATA  0x01u
#define WSC_FRAME_TYPE_STATUS 0x02u
#define WSC_HEADER_LEN       46u
#define WSC_CSI_MAX_LEN      1024u
#define WSC_STATUS_PAYLOAD_LEN 36u
#define WSC_FRAME_MAX_LEN    (WSC_HEADER_LEN + WSC_CSI_MAX_LEN + 4u)

/* ESP-NOW TX payload (24 bytes, little-endian). */
#define WSC_TX_PAYLOAD_MAGIC 0x58435357u /* 'W','S','C','X' */
#define WSC_TX_PAYLOAD_LEN   24u

/* PHY flags bit assignments in the frame header. */
#define WSC_PHY_FLAG_HT40          0x01u
#define WSC_PHY_FLAG_SIG_MODE_HT   0x02u
#define WSC_PHY_FLAG_STBC          0x04u
#define WSC_PHY_FLAG_AGGREGATION   0x08u
#define WSC_PHY_FLAG_SGI           0x10u
#define WSC_PHY_FLAG_SMOOTHING     0x20u
#define WSC_PHY_FLAG_NOT_SOUNDING  0x40u
#define WSC_PHY_FLAG_RESERVED      0x80u

typedef struct {
    uint32_t magic;
    uint8_t version;
    uint8_t frame_type;
    uint16_t header_len;
    uint16_t payload_len;
    uint32_t seq;
    uint64_t device_ts_us;
    uint32_t rx_id;
    uint64_t tx_id_hash;
    uint8_t channel;
    uint8_t bandwidth_mhz; /* 20 or 40 */
    int16_t rssi_dbm_x100;
    int16_t noise_floor_dbm_x100;
    uint8_t phy_flags;
    uint8_t first_word_invalid;
    uint16_t csi_len;
    uint16_t reserved;
} wsc_frame_header_t;

/* Fixed 36-byte status payload (frame_type = WSC_FRAME_TYPE_STATUS). */
typedef struct {
    uint32_t uptime_s;
    uint32_t free_heap;
    uint32_t counter_received;
    uint32_t counter_filtered;
    uint32_t counter_ring_overflow;
    uint32_t counter_serial_drop;
    uint32_t counter_bad_length;
    int16_t last_rssi_dbm_x100;
    int16_t last_noise_floor_dbm_x100;
    uint8_t reserved[4];
} wsc_status_payload_t;

size_t wsc_frame_header_size(void);

/* Encode one CSI data frame; csi_len must equal payload_len. */
bool wsc_encode_data_frame(uint8_t *out, size_t out_cap, size_t *out_len,
                           const wsc_frame_header_t *hdr,
                           const uint8_t *csi_bytes);

/* Encode one status frame; csi_len must be 0. */
bool wsc_encode_status_frame(uint8_t *out, size_t out_cap, size_t *out_len,
                             const wsc_frame_header_t *hdr,
                             const wsc_status_payload_t *status);

/* ESP-NOW TX payload (24 bytes): magic, version, reserved, len, tx_id,
 * seq, tx timestamp. */
size_t wsc_tx_payload_size(void);
bool wsc_encode_tx_payload(uint8_t *out, size_t out_cap, size_t *out_len,
                           uint32_t tx_id, uint32_t seq, uint64_t tx_ts_us);
bool wsc_parse_tx_payload(const uint8_t *buf, size_t len,
                          uint32_t *tx_id, uint32_t *seq, uint64_t *tx_ts_us);

/* Signed sequence gap with uint32 wrap-around; defined for |gap| < 2^31. */
int32_t wsc_seq_gap(uint32_t prev, uint32_t curr);

#ifdef __cplusplus
}
#endif

#endif /* WSC_WIRE_PROTOCOL_H */
