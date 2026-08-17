/*
 * Host-side golden test for the wire protocol C encoder.
 *
 * Compiled without ESP-IDF (pure C) and compared byte-for-byte against the
 * Python reference encoder in tests/firmware_contract.
 *
 * SPDX-License-Identifier: Apache-2.0
 */

#include <stdio.h>
#include <string.h>

#include "crc32.h"
#include "wire_protocol.h"

static int print_hex(const char *label, const uint8_t *data, size_t len)
{
    printf("%s:", label);
    for (size_t i = 0; i < len; i++) {
        printf("%02x", data[i]);
    }
    printf("\n");
    return 0;
}

int main(void)
{
    /* Known CRC-32 vector: crc32("123456789") == 0xCBF43926. */
    const uint8_t check[9] = "123456789";
    if (wsc_crc32(check, sizeof(check)) != 0xCBF43926u) {
        fprintf(stderr, "crc32 known-answer test failed\n");
        return 1;
    }

    const uint8_t csi[8] = {0x00, 0x01, 0x02, 0x03, 0xFE, 0xFD, 0x7F, 0x80};

    wsc_frame_header_t hdr;
    memset(&hdr, 0, sizeof(hdr));
    hdr.magic = WSC_MAGIC_U32;
    hdr.version = WSC_PROTOCOL_VERSION;
    hdr.frame_type = WSC_FRAME_TYPE_DATA;
    hdr.header_len = WSC_HEADER_LEN;
    hdr.payload_len = sizeof(csi);
    hdr.seq = 0xDEADBEEFu;
    hdr.device_ts_us = 0x0102030405060708ULL;
    hdr.rx_id = 1u;
    hdr.tx_id_hash = 0x1122334455667788ULL;
    hdr.channel = 6;
    hdr.bandwidth_mhz = 20;
    hdr.rssi_dbm_x100 = -6500;
    hdr.noise_floor_dbm_x100 = -9500;
    hdr.phy_flags = WSC_PHY_FLAG_SIG_MODE_HT;
    hdr.first_word_invalid = 0;
    hdr.csi_len = sizeof(csi);
    hdr.reserved = 0;

    uint8_t buf[WSC_FRAME_MAX_LEN];
    size_t len = 0;
    if (!wsc_encode_data_frame(buf, sizeof(buf), &len, &hdr, csi)) {
        return 2;
    }
    print_hex("data_frame", buf, len);

    wsc_status_payload_t status;
    memset(&status, 0, sizeof(status));
    status.uptime_s = 42;
    status.free_heap = 0x123456;
    status.counter_received = 1000;
    status.counter_filtered = 3;
    status.counter_ring_overflow = 1;
    status.counter_serial_drop = 2;
    status.counter_bad_length = 0;
    status.last_rssi_dbm_x100 = -6600;
    status.last_noise_floor_dbm_x100 = -9400;

    memset(&hdr, 0, sizeof(hdr));
    hdr.magic = WSC_MAGIC_U32;
    hdr.version = WSC_PROTOCOL_VERSION;
    hdr.frame_type = WSC_FRAME_TYPE_STATUS;
    hdr.header_len = WSC_HEADER_LEN;
    hdr.payload_len = WSC_STATUS_PAYLOAD_LEN;
    hdr.seq = 42;
    hdr.device_ts_us = 0x0102030405060708ULL;
    hdr.rx_id = 1u;
    hdr.tx_id_hash = 0x1122334455667788ULL;
    hdr.channel = 6;
    hdr.bandwidth_mhz = 20;
    hdr.rssi_dbm_x100 = -6600;
    hdr.noise_floor_dbm_x100 = -9400;
    hdr.csi_len = 0;
    if (!wsc_encode_status_frame(buf, sizeof(buf), &len, &hdr, &status)) {
        return 3;
    }
    print_hex("status_frame", buf, len);

    if (!wsc_encode_tx_payload(buf, sizeof(buf), &len, 7u, 0xF0F0F0F0u,
                               0x0102030405060708ULL)) {
        return 4;
    }
    print_hex("tx_payload", buf, len);

    if (wsc_seq_gap(0xFFFFFFFFu, 2u) != 3) {
        return 5;
    }
    if (wsc_seq_gap(2u, 0xFFFFFFFFu) != -3) {
        return 6;
    }
    return 0;
}
