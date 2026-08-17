/*
 * WiFi Spatial Council — CRC-32 (IEEE 802.3, zlib-compatible).
 *
 * SPDX-License-Identifier: Apache-2.0
 */
#include "crc32.h"

static uint32_t s_crc_table[256];
static int s_crc_table_ready = 0;

static void crc32_init_table(void)
{
    for (uint32_t i = 0; i < 256; i++) {
        uint32_t crc = i;
        for (int bit = 0; bit < 8; bit++) {
            crc = (crc & 1u) ? (crc >> 1) ^ 0xEDB88320u : (crc >> 1);
        }
        s_crc_table[i] = crc;
    }
    s_crc_table_ready = 1;
}

uint32_t wsc_crc32(const uint8_t *data, size_t len)
{
    if (!s_crc_table_ready) {
        crc32_init_table();
    }
    uint32_t crc = 0xFFFFFFFFu;
    for (size_t i = 0; i < len; i++) {
        crc = (crc >> 8) ^ s_crc_table[(crc ^ data[i]) & 0xFFu];
    }
    return crc ^ 0xFFFFFFFFu;
}
