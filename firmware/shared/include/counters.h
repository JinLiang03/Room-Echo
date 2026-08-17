/*
 * WiFi Spatial Council — monotonic runtime counters.
 *
 * Counters are uint32 and wrap by design; consumers compute deltas.
 * Increments from the Wi-Fi callback use relaxed atomics.
 *
 * SPDX-License-Identifier: Apache-2.0
 */
#ifndef WSC_COUNTERS_H
#define WSC_COUNTERS_H

#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

typedef struct {
    uint32_t received;         /* CSI callbacks accepted after MAC filter */
    uint32_t filtered;         /* rejected (wrong MAC / bad payload) */
    uint32_t ring_overflow;    /* pool full drops */
    uint32_t serial_drop;      /* UART write failures */
    uint32_t bad_length;       /* CSI length exceeds configured maximum */
} wsc_counters_t;

static inline void wsc_counter_add(uint32_t *counter, uint32_t delta)
{
    __atomic_fetch_add(counter, delta, __ATOMIC_RELAXED);
}

static inline uint32_t wsc_counter_load(const uint32_t *counter)
{
    return __atomic_load_n(counter, __ATOMIC_RELAXED);
}

#ifdef __cplusplus
}
#endif

#endif /* WSC_COUNTERS_H */
