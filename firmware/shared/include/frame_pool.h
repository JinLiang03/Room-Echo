/*
 * WiFi Spatial Council — fixed-size slot pool for CSI frames.
 *
 * Single producer (Wi-Fi CSI callback) / single consumer (serializer task).
 * The producer never blocks: if the pool is full the frame is dropped and the
 * overflow counter is incremented. Indexes are managed with acquire/release
 * atomics so the callback may run on either core.
 *
 * SPDX-License-Identifier: Apache-2.0
 */
#ifndef WSC_FRAME_POOL_H
#define WSC_FRAME_POOL_H

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

typedef struct {
    uint8_t *slots;        /* slot_count * slot_size bytes, caller-owned */
    uint16_t *slot_lens;   /* slot_count entries, caller-owned */
    uint32_t slot_count;
    uint32_t slot_size;
    volatile uint32_t write_idx;
    volatile uint32_t read_idx;
    volatile uint32_t overflow_drops;
} wsc_frame_pool_t;

void wsc_frame_pool_init(wsc_frame_pool_t *pool, uint8_t *slots,
                         uint16_t *slot_lens, uint32_t slot_count,
                         uint32_t slot_size);

/* Copy one frame into the pool. Returns false (and counts a drop) when full.
 * Never blocks. len must be <= slot_size. */
bool wsc_frame_pool_try_enqueue(wsc_frame_pool_t *pool, const uint8_t *data,
                                size_t len);

/* Returns a pointer to the oldest frame and its length, or NULL when empty. */
const uint8_t *wsc_frame_pool_peek(const wsc_frame_pool_t *pool,
                                   size_t *len_out);

/* Release the oldest frame after it has been serialized. */
void wsc_frame_pool_consume(wsc_frame_pool_t *pool);

uint32_t wsc_frame_pool_overflow_count(const wsc_frame_pool_t *pool);

#ifdef __cplusplus
}
#endif

#endif /* WSC_FRAME_POOL_H */
