/*
 * WiFi Spatial Council — fixed-size slot pool implementation.
 *
 * SPDX-License-Identifier: Apache-2.0
 */
#include "frame_pool.h"

#include <string.h>

void wsc_frame_pool_init(wsc_frame_pool_t *pool, uint8_t *slots,
                         uint16_t *slot_lens, uint32_t slot_count,
                         uint32_t slot_size)
{
    pool->slots = slots;
    pool->slot_lens = slot_lens;
    pool->slot_count = slot_count;
    pool->slot_size = slot_size;
    pool->write_idx = 0;
    pool->read_idx = 0;
    pool->overflow_drops = 0;
    memset(slots, 0, (size_t)slot_count * slot_size);
    memset(slot_lens, 0, (size_t)slot_count * sizeof(uint16_t));
}

bool wsc_frame_pool_try_enqueue(wsc_frame_pool_t *pool, const uint8_t *data,
                                size_t len)
{
    if (pool == NULL || data == NULL) {
        return false;
    }
    if (len == 0 || len > pool->slot_size) {
        return false;
    }
    const uint32_t write_idx =
        __atomic_load_n(&pool->write_idx, __ATOMIC_ACQUIRE);
    const uint32_t read_idx =
        __atomic_load_n(&pool->read_idx, __ATOMIC_ACQUIRE);
    /* N slots hold at most N-1 frames so full and empty stay distinct. */
    if (write_idx - read_idx >= pool->slot_count - 1) {
        __atomic_fetch_add(&pool->overflow_drops, 1, __ATOMIC_RELAXED);
        return false;
    }
    uint8_t *slot = pool->slots + (size_t)(write_idx % pool->slot_count) * pool->slot_size;
    memcpy(slot, data, len);
    pool->slot_lens[write_idx % pool->slot_count] = (uint16_t)len;
    __atomic_store_n(&pool->write_idx, write_idx + 1, __ATOMIC_RELEASE);
    return true;
}

const uint8_t *wsc_frame_pool_peek(const wsc_frame_pool_t *pool,
                                   size_t *len_out)
{
    if (pool == NULL || len_out == NULL) {
        return NULL;
    }
    const uint32_t write_idx =
        __atomic_load_n(&pool->write_idx, __ATOMIC_ACQUIRE);
    const uint32_t read_idx =
        __atomic_load_n(&pool->read_idx, __ATOMIC_ACQUIRE);
    if (read_idx == write_idx) {
        return NULL;
    }
    *len_out = pool->slot_lens[read_idx % pool->slot_count];
    return pool->slots + (size_t)(read_idx % pool->slot_count) * pool->slot_size;
}

void wsc_frame_pool_consume(wsc_frame_pool_t *pool)
{
    if (pool == NULL) {
        return;
    }
    const uint32_t read_idx =
        __atomic_load_n(&pool->read_idx, __ATOMIC_ACQUIRE);
    __atomic_store_n(&pool->read_idx, read_idx + 1, __ATOMIC_RELEASE);
}

uint32_t wsc_frame_pool_overflow_count(const wsc_frame_pool_t *pool)
{
    if (pool == NULL) {
        return 0;
    }
    return __atomic_load_n(&pool->overflow_drops, __ATOMIC_RELAXED);
}
