/*
 * WiFi Spatial Council — CRC-32 (IEEE 802.3, zlib-compatible).
 *
 * SPDX-License-Identifier: Apache-2.0
 */
#ifndef WSC_CRC32_H
#define WSC_CRC32_H

#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

/* Standard CRC-32 as used by zlib: init 0xFFFFFFFF, final xor 0xFFFFFFFF. */
uint32_t wsc_crc32(const uint8_t *data, size_t len);

#ifdef __cplusplus
}
#endif

#endif /* WSC_CRC32_H */
