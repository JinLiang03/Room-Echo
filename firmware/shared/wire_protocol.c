/*
 * WiFi Spatial Council — binary wire protocol implementation.
 *
 * The on-wire layout is explicit little-endian packing; never a raw struct
 * dump. All lengths are bounds-checked before writing.
 *
 * SPDX-License-Identifier: Apache-2.0
 */
#include "wire_protocol.h"

#include <string.h>

#include "crc32.h"

static void put_u16le(uint8_t *p, uint16_t v)
{
    p[0] = (uint8_t)(v & 0xFFu);
    p[1] = (uint8_t)((v >> 8) & 0xFFu);
}

static void put_u32le(uint8_t *p, uint32_t v)
{
    p[0] = (uint8_t)(v & 0xFFu);
    p[1] = (uint8_t)((v >> 8) & 0xFFu);
    p[2] = (uint8_t)((v >> 16) & 0xFFu);
    p[3] = (uint8_t)((v >> 24) & 0xFFu);
}

static void put_u64le(uint8_t *p, uint64_t v)
{
    for (int i = 0; i < 8; i++) {
        p[i] = (uint8_t)((v >> (8 * i)) & 0xFFu);
    }
}

static void put_i16le(uint8_t *p, int16_t v)
{
    put_u16le(p, (uint16_t)v);
}

static uint32_t get_u32le(const uint8_t *p)
{
    return (uint32_t)p[0] | ((uint32_t)p[1] << 8) | ((uint32_t)p[2] << 16) |
           ((uint32_t)p[3] << 24);
}

static uint64_t get_u64le(const uint8_t *p)
{
    uint64_t v = 0;
    for (int i = 0; i < 8; i++) {
        v |= (uint64_t)p[i] << (8 * i);
    }
    return v;
}

static bool encode_header(uint8_t *out, size_t out_cap,
                          const wsc_frame_header_t *hdr)
{
    if (hdr == NULL || out == NULL) {
        return false;
    }
    if (hdr->magic != WSC_MAGIC_U32) {
        return false;
    }
    if (hdr->version != WSC_PROTOCOL_VERSION) {
        return false;
    }
    if (hdr->header_len != WSC_HEADER_LEN) {
        return false;
    }
    if (hdr->bandwidth_mhz != 20 && hdr->bandwidth_mhz != 40) {
        return false;
    }
    if (out_cap < WSC_HEADER_LEN) {
        return false;
    }

    size_t o = 0;
    put_u32le(out + o, hdr->magic);
    o += 4;
    out[o++] = hdr->version;
    out[o++] = hdr->frame_type;
    put_u16le(out + o, hdr->header_len);
    o += 2;
    put_u16le(out + o, hdr->payload_len);
    o += 2;
    put_u32le(out + o, hdr->seq);
    o += 4;
    put_u64le(out + o, hdr->device_ts_us);
    o += 8;
    put_u32le(out + o, hdr->rx_id);
    o += 4;
    put_u64le(out + o, hdr->tx_id_hash);
    o += 8;
    out[o++] = hdr->channel;
    out[o++] = hdr->bandwidth_mhz;
    put_i16le(out + o, hdr->rssi_dbm_x100);
    o += 2;
    put_i16le(out + o, hdr->noise_floor_dbm_x100);
    o += 2;
    out[o++] = hdr->phy_flags;
    out[o++] = hdr->first_word_invalid ? 1u : 0u;
    put_u16le(out + o, hdr->csi_len);
    o += 2;
    put_u16le(out + o, hdr->reserved);
    o += 2;
    return o == WSC_HEADER_LEN;
}

size_t wsc_frame_header_size(void)
{
    return WSC_HEADER_LEN;
}

bool wsc_encode_data_frame(uint8_t *out, size_t out_cap, size_t *out_len,
                           const wsc_frame_header_t *hdr,
                           const uint8_t *csi_bytes)
{
    if (out_len == NULL || hdr == NULL) {
        return false;
    }
    if (hdr->frame_type != WSC_FRAME_TYPE_DATA) {
        return false;
    }
    if (hdr->payload_len != hdr->csi_len) {
        return false;
    }
    if (hdr->csi_len > WSC_CSI_MAX_LEN) {
        return false;
    }
    if (hdr->csi_len > 0 && csi_bytes == NULL) {
        return false;
    }
    const size_t total = WSC_HEADER_LEN + hdr->csi_len + 4u;
    if (out_cap < total) {
        return false;
    }
    if (!encode_header(out, out_cap, hdr)) {
        return false;
    }
    if (hdr->csi_len > 0) {
        memcpy(out + WSC_HEADER_LEN, csi_bytes, hdr->csi_len);
    }
    const uint32_t crc = wsc_crc32(out, WSC_HEADER_LEN + hdr->csi_len);
    put_u32le(out + WSC_HEADER_LEN + hdr->csi_len, crc);
    *out_len = total;
    return true;
}

bool wsc_encode_status_frame(uint8_t *out, size_t out_cap, size_t *out_len,
                             const wsc_frame_header_t *hdr,
                             const wsc_status_payload_t *status)
{
    if (out_len == NULL || hdr == NULL || status == NULL) {
        return false;
    }
    if (hdr->frame_type != WSC_FRAME_TYPE_STATUS) {
        return false;
    }
    if (hdr->payload_len != WSC_STATUS_PAYLOAD_LEN || hdr->csi_len != 0) {
        return false;
    }
    const size_t total = WSC_HEADER_LEN + WSC_STATUS_PAYLOAD_LEN + 4u;
    if (out_cap < total) {
        return false;
    }
    if (!encode_header(out, out_cap, hdr)) {
        return false;
    }
    uint8_t *p = out + WSC_HEADER_LEN;
    put_u32le(p, status->uptime_s);
    p += 4;
    put_u32le(p, status->free_heap);
    p += 4;
    put_u32le(p, status->counter_received);
    p += 4;
    put_u32le(p, status->counter_filtered);
    p += 4;
    put_u32le(p, status->counter_ring_overflow);
    p += 4;
    put_u32le(p, status->counter_serial_drop);
    p += 4;
    put_u32le(p, status->counter_bad_length);
    p += 4;
    put_i16le(p, status->last_rssi_dbm_x100);
    p += 2;
    put_i16le(p, status->last_noise_floor_dbm_x100);
    p += 2;
    memset(p, 0, 4);
    const uint32_t crc = wsc_crc32(out, WSC_HEADER_LEN + WSC_STATUS_PAYLOAD_LEN);
    put_u32le(out + WSC_HEADER_LEN + WSC_STATUS_PAYLOAD_LEN, crc);
    *out_len = total;
    return true;
}

size_t wsc_tx_payload_size(void)
{
    return WSC_TX_PAYLOAD_LEN;
}

bool wsc_encode_tx_payload(uint8_t *out, size_t out_cap, size_t *out_len,
                           uint32_t tx_id, uint32_t seq, uint64_t tx_ts_us)
{
    if (out == NULL || out_len == NULL || out_cap < WSC_TX_PAYLOAD_LEN) {
        return false;
    }
    size_t o = 0;
    put_u32le(out + o, WSC_TX_PAYLOAD_MAGIC);
    o += 4;
    out[o++] = WSC_PROTOCOL_VERSION;
    out[o++] = 0; /* reserved */
    put_u16le(out + o, WSC_TX_PAYLOAD_LEN);
    o += 2;
    put_u32le(out + o, tx_id);
    o += 4;
    put_u32le(out + o, seq);
    o += 4;
    put_u64le(out + o, tx_ts_us);
    o += 8;
    *out_len = o;
    return o == WSC_TX_PAYLOAD_LEN;
}

bool wsc_parse_tx_payload(const uint8_t *buf, size_t len,
                          uint32_t *tx_id, uint32_t *seq, uint64_t *tx_ts_us)
{
    if (buf == NULL || tx_id == NULL || seq == NULL || tx_ts_us == NULL) {
        return false;
    }
    if (len < WSC_TX_PAYLOAD_LEN) {
        return false;
    }
    if (get_u32le(buf) != WSC_TX_PAYLOAD_MAGIC) {
        return false;
    }
    if (buf[4] != WSC_PROTOCOL_VERSION) {
        return false;
    }
    const uint16_t payload_len = (uint16_t)(buf[6] | ((uint16_t)buf[7] << 8));
    if (payload_len != WSC_TX_PAYLOAD_LEN) {
        return false;
    }
    *tx_id = get_u32le(buf + 8);
    *seq = get_u32le(buf + 12);
    *tx_ts_us = get_u64le(buf + 16);
    return true;
}

int32_t wsc_seq_gap(uint32_t prev, uint32_t curr)
{
    const uint32_t diff = curr - prev;
    if (diff >= 0x80000000u) {
        return (int32_t)(diff - 0x100000000u);
    }
    return (int32_t)diff;
}
