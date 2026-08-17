/*
 * Host-side test for the frame pool: full-pool drop with counter, drain
 * without deadlock, and length validation.
 *
 * SPDX-License-Identifier: Apache-2.0
 */

#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>

#include "frame_pool.h"

int main(void)
{
    enum {
        SLOTS = 4,
        SLOT_SIZE = 64,
    };
    static uint8_t mem[SLOTS * SLOT_SIZE];
    static uint16_t lens[SLOTS];
    wsc_frame_pool_t pool;
    wsc_frame_pool_init(&pool, mem, lens, SLOTS, SLOT_SIZE);

    uint8_t frame[SLOT_SIZE];
    for (size_t i = 0; i < sizeof(frame); i++) {
        frame[i] = (uint8_t)i;
    }

    /* Capacity is SLOTS - 1 usable slots. */
    for (int i = 0; i < SLOTS - 1; i++) {
        assert(wsc_frame_pool_try_enqueue(&pool, frame, 16));
    }
    /* Full: drop and count, never block. */
    assert(!wsc_frame_pool_try_enqueue(&pool, frame, 16));
    assert(wsc_frame_pool_overflow_count(&pool) == 1);

    /* Drain everything; no deadlock, contents intact. */
    size_t got = 0;
    const uint8_t *p;
    while ((p = wsc_frame_pool_peek(&pool, &got)) != NULL) {
        assert(got == 16);
        assert(memcmp(p, frame, 16) == 0);
        wsc_frame_pool_consume(&pool);
    }
    assert(wsc_frame_pool_peek(&pool, &got) == NULL);
    assert(wsc_frame_pool_overflow_count(&pool) == 1);

    /* Oversized frames are rejected without touching the overflow counter. */
    assert(!wsc_frame_pool_try_enqueue(&pool, frame, SLOT_SIZE + 1));
    assert(wsc_frame_pool_overflow_count(&pool) == 1);

    printf("frame_pool_test OK\n");
    return 0;
}
