/*
 * WiFi Spatial Council — CSI receiver with binary serial output.
 *
 * The Wi-Fi CSI callback only filters, packs, and enqueues into a fixed-size
 * slot pool. All serialization and UART writes happen in a separate task, so
 * the callback never blocks or performs I/O.
 *
 * Based on the Espressif esp-csi get-started example (commit
 * 8633d67152db2808f141cc1595970aa9cf406045), reworked per
 * docs/WIRE_PROTOCOL.md: no CSV/printf in the callback, binary frames with
 * magic/version/length/CRC, status frames separate from data frames.
 *
 * SPDX-License-Identifier: Apache-2.0
 */

#include <stdint.h>
#include <string.h>

#include "counters.h"
#include "driver/uart.h"
#include "esp_event.h"
#include "esp_mac.h"
#include "esp_netif.h"
#include "esp_now.h"
#include "esp_timer.h"
#include "esp_wifi.h"
#include "frame_pool.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "nvs_flash.h"
#include "wire_protocol.h"

static const uint8_t s_tx_mac[6] = {
    CONFIG_WSC_TX_MAC_0,
    CONFIG_WSC_TX_MAC_1,
    CONFIG_WSC_TX_MAC_2,
    CONFIG_WSC_TX_MAC_3,
    CONFIG_WSC_TX_MAC_4,
    CONFIG_WSC_TX_MAC_5,
};

static const uint8_t s_broadcast_mac[6] = {0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF};

static wsc_counters_t s_counters;
static wsc_frame_pool_t s_pool;
static uint8_t s_pool_slots[CONFIG_WSC_CSI_SLOTS * WSC_FRAME_MAX_LEN];
static uint16_t s_pool_lens[CONFIG_WSC_CSI_SLOTS];
static uint8_t s_encode_buf[WSC_FRAME_MAX_LEN];
static uint64_t s_tx_id_hash;
static volatile int16_t s_last_rssi_dbm_x100;
static volatile int16_t s_last_noise_floor_dbm_x100;

static uint64_t tx_mac_hash(const uint8_t mac[6])
{
    uint64_t hash = 0xcbf29ce484222325ULL; /* FNV-1a 64 offset basis */
    for (int i = 0; i < 6; i++) {
        hash ^= mac[i];
        hash *= 0x100000001b3ULL;
    }
    return hash;
}

static void wifi_init(void)
{
    ESP_ERROR_CHECK(esp_event_loop_create_default());
    ESP_ERROR_CHECK(esp_netif_init());

    wifi_init_config_t cfg = WIFI_INIT_CONFIG_DEFAULT();
    ESP_ERROR_CHECK(esp_wifi_init(&cfg));
    ESP_ERROR_CHECK(esp_wifi_set_mode(WIFI_MODE_STA));
    ESP_ERROR_CHECK(esp_wifi_set_storage(WIFI_STORAGE_RAM));
    ESP_ERROR_CHECK(esp_wifi_set_bandwidth(WIFI_IF_STA, WIFI_BW_HT20));
    ESP_ERROR_CHECK(esp_wifi_start());
    ESP_ERROR_CHECK(esp_wifi_set_ps(WIFI_PS_NONE));
    ESP_ERROR_CHECK(
        esp_wifi_set_channel(CONFIG_WSC_RX_CHANNEL, WIFI_SECOND_CHAN_NONE));
    /* Follows the esp-csi get-started example: RX uses the configured TX MAC. */
    ESP_ERROR_CHECK(esp_wifi_set_mac(WIFI_IF_STA, s_tx_mac));
}

static void esp_now_init_broadcast(void)
{
    ESP_ERROR_CHECK(esp_now_init());

    esp_now_peer_info_t peer = {
        .channel = CONFIG_WSC_RX_CHANNEL,
        .ifidx = WIFI_IF_STA,
        .encrypt = false,
    };
    memcpy(peer.peer_addr, s_broadcast_mac, sizeof(peer.peer_addr));
    ESP_ERROR_CHECK(esp_now_add_peer(&peer));
}

static void wifi_csi_rx_cb(void *ctx, wifi_csi_info_t *info)
{
    (void)ctx;

    if (info == NULL || info->buf == NULL || info->len == 0) {
        return;
    }
    if (memcmp(info->mac, s_tx_mac, sizeof(s_tx_mac)) != 0) {
        wsc_counter_add(&s_counters.filtered, 1);
        return;
    }
    wsc_counter_add(&s_counters.received, 1);

    uint32_t tx_id = 0;
    uint32_t tx_seq = 0;
    uint64_t tx_ts_us = 0;
    if (info->payload == NULL || info->payload_len < WSC_TX_PAYLOAD_LEN ||
        !wsc_parse_tx_payload(info->payload, info->payload_len, &tx_id,
                              &tx_seq, &tx_ts_us)) {
        wsc_counter_add(&s_counters.filtered, 1);
        return;
    }
    if (info->len > WSC_CSI_MAX_LEN) {
        wsc_counter_add(&s_counters.bad_length, 1);
        return;
    }

    const wifi_pkt_rx_ctrl_t *rx_ctrl = &info->rx_ctrl;
    wsc_frame_header_t hdr;
    memset(&hdr, 0, sizeof(hdr));
    hdr.magic = WSC_MAGIC_U32;
    hdr.version = WSC_PROTOCOL_VERSION;
    hdr.frame_type = WSC_FRAME_TYPE_DATA;
    hdr.header_len = WSC_HEADER_LEN;
    hdr.payload_len = (uint16_t)info->len;
    hdr.seq = tx_seq;
    hdr.device_ts_us = tx_ts_us;
    hdr.rx_id = CONFIG_WSC_RX_ID;
    hdr.tx_id_hash = s_tx_id_hash;
    hdr.channel = (uint8_t)rx_ctrl->channel;
    /* rx_ctrl->cwb is a 1-bit field: 0 = 20 MHz, 1 = 40 MHz. */
    hdr.bandwidth_mhz = (rx_ctrl->cwb == 1) ? 40 : 20;
    hdr.rssi_dbm_x100 = (int16_t)(rx_ctrl->rssi * 100);
    hdr.noise_floor_dbm_x100 = (int16_t)(rx_ctrl->noise_floor * 100);
    hdr.phy_flags = 0;
    if (rx_ctrl->cwb == 1) {
        hdr.phy_flags |= WSC_PHY_FLAG_HT40;
    }
    /* rx_ctrl->sig_mode is a 2-bit field: 1 = HT (11n). */
    if (rx_ctrl->sig_mode == 1) {
        hdr.phy_flags |= WSC_PHY_FLAG_SIG_MODE_HT;
    }
    if (rx_ctrl->stbc) {
        hdr.phy_flags |= WSC_PHY_FLAG_STBC;
    }
    if (rx_ctrl->aggregation) {
        hdr.phy_flags |= WSC_PHY_FLAG_AGGREGATION;
    }
    if (rx_ctrl->sgi) {
        hdr.phy_flags |= WSC_PHY_FLAG_SGI;
    }
    if (rx_ctrl->smoothing) {
        hdr.phy_flags |= WSC_PHY_FLAG_SMOOTHING;
    }
    if (rx_ctrl->not_sounding) {
        hdr.phy_flags |= WSC_PHY_FLAG_NOT_SOUNDING;
    }
    hdr.first_word_invalid = info->first_word_invalid ? 1u : 0u;
    hdr.csi_len = (uint16_t)info->len;

    size_t frame_len = 0;
    /* info->buf is int8_t* per ESP-IDF; the wire treats CSI as raw bytes. */
    if (!wsc_encode_data_frame(s_encode_buf, sizeof(s_encode_buf), &frame_len,
                               &hdr, (const uint8_t *)info->buf)) {
        wsc_counter_add(&s_counters.bad_length, 1);
        return;
    }
    __atomic_store_n(&s_last_rssi_dbm_x100, hdr.rssi_dbm_x100,
                     __ATOMIC_RELAXED);
    __atomic_store_n(&s_last_noise_floor_dbm_x100,
                     hdr.noise_floor_dbm_x100, __ATOMIC_RELAXED);

    if (!wsc_frame_pool_try_enqueue(&s_pool, s_encode_buf, frame_len)) {
        /* Pool counts overflow_drops; never blocks, never loops. */
        return;
    }
}

static void wifi_csi_init(void)
{
    ESP_ERROR_CHECK(esp_wifi_set_promiscuous(true));

    wifi_csi_config_t csi_config = {
        .lltf_en = true,
        .htltf_en = true,
        .stbc_htltf2_en = true,
        .ltf_merge_en = true,
        .channel_filter_en = true,
        .manu_scale = false,
        .shift = false,
    };
    ESP_ERROR_CHECK(esp_wifi_set_csi_config(&csi_config));
    ESP_ERROR_CHECK(esp_wifi_set_csi_rx_cb(wifi_csi_rx_cb, NULL));
    ESP_ERROR_CHECK(esp_wifi_set_csi(true));
}

static void serial_init(void)
{
    const uart_config_t uart_config = {
        .baud_rate = CONFIG_WSC_SERIAL_BAUD,
        .data_bits = UART_DATA_8_BITS,
        .parity = UART_PARITY_DISABLE,
        .stop_bits = UART_STOP_BITS_1,
        .flow_ctrl = UART_HW_FLOWCTRL_DISABLE,
        .source_clk = UART_SCLK_DEFAULT,
    };
    ESP_ERROR_CHECK(uart_driver_install(CONFIG_WSC_SERIAL_UART, 256,
                                        CONFIG_WSC_SERIAL_TX_BUF_SIZE, 0,
                                        NULL, 0));
    ESP_ERROR_CHECK(uart_param_config(CONFIG_WSC_SERIAL_UART, &uart_config));
    ESP_ERROR_CHECK(uart_set_pin(CONFIG_WSC_SERIAL_UART,
                                 CONFIG_WSC_SERIAL_TX_GPIO,
                                 UART_PIN_NO_CHANGE, UART_PIN_NO_CHANGE,
                                 UART_PIN_NO_CHANGE));
}

static void serializer_task(void *arg)
{
    (void)arg;
    for (;;) {
        size_t len = 0;
        const uint8_t *frame = wsc_frame_pool_peek(&s_pool, &len);
        if (frame == NULL) {
            vTaskDelay(pdMS_TO_TICKS(1));
            continue;
        }
        const int written =
            uart_write_bytes(CONFIG_WSC_SERIAL_UART, frame, len);
        if (written != (int)len) {
            wsc_counter_add(&s_counters.serial_drop, 1);
        }
        wsc_frame_pool_consume(&s_pool);
    }
}

static void status_task(void *arg)
{
    (void)arg;
    uint8_t frame[WSC_HEADER_LEN + WSC_STATUS_PAYLOAD_LEN + 4];
    TickType_t last_wake = xTaskGetTickCount();
    for (;;) {
        vTaskDelayUntil(&last_wake, pdMS_TO_TICKS(1000));

        wsc_status_payload_t status;
        memset(&status, 0, sizeof(status));
        status.uptime_s =
            (uint32_t)(xTaskGetTickCount() / (TickType_t)configTICK_RATE_HZ);
        status.free_heap = (uint32_t)esp_get_free_heap_size();
        status.counter_received = wsc_counter_load(&s_counters.received);
        status.counter_filtered = wsc_counter_load(&s_counters.filtered);
        status.counter_ring_overflow =
            wsc_frame_pool_overflow_count(&s_pool);
        status.counter_serial_drop = wsc_counter_load(&s_counters.serial_drop);
        status.counter_bad_length = wsc_counter_load(&s_counters.bad_length);
        status.last_rssi_dbm_x100 =
            __atomic_load_n(&s_last_rssi_dbm_x100, __ATOMIC_RELAXED);
        status.last_noise_floor_dbm_x100 =
            __atomic_load_n(&s_last_noise_floor_dbm_x100, __ATOMIC_RELAXED);

        wsc_frame_header_t hdr;
        memset(&hdr, 0, sizeof(hdr));
        hdr.magic = WSC_MAGIC_U32;
        hdr.version = WSC_PROTOCOL_VERSION;
        hdr.frame_type = WSC_FRAME_TYPE_STATUS;
        hdr.header_len = WSC_HEADER_LEN;
        hdr.payload_len = WSC_STATUS_PAYLOAD_LEN;
        hdr.seq = status.uptime_s;
        hdr.device_ts_us = (uint64_t)esp_timer_get_time();
        hdr.rx_id = CONFIG_WSC_RX_ID;
        hdr.tx_id_hash = s_tx_id_hash;
        hdr.channel = CONFIG_WSC_RX_CHANNEL;
        hdr.bandwidth_mhz = 20;
        hdr.rssi_dbm_x100 = status.last_rssi_dbm_x100;
        hdr.noise_floor_dbm_x100 = status.last_noise_floor_dbm_x100;
        hdr.csi_len = 0;

        size_t len = 0;
        if (wsc_encode_status_frame(frame, sizeof(frame), &len, &hdr,
                                    &status)) {
            const int written =
                uart_write_bytes(CONFIG_WSC_SERIAL_UART, frame, len);
            if (written != (int)len) {
                wsc_counter_add(&s_counters.serial_drop, 1);
            }
        }
    }
}

void app_main(void)
{
    esp_err_t ret = nvs_flash_init();
    if (ret == ESP_ERR_NVS_NO_FREE_PAGES || ret == ESP_ERR_NVS_NEW_VERSION_FOUND) {
        ESP_ERROR_CHECK(nvs_flash_erase());
        ret = nvs_flash_init();
    }
    ESP_ERROR_CHECK(ret);

    s_tx_id_hash = tx_mac_hash(s_tx_mac);
    wsc_frame_pool_init(&s_pool, s_pool_slots, s_pool_lens,
                        CONFIG_WSC_CSI_SLOTS, WSC_FRAME_MAX_LEN);

    wifi_init();
    esp_now_init_broadcast();
    wifi_csi_init();
    serial_init();

    xTaskCreate(serializer_task, "csi_serial", 4096, NULL, 6, NULL);
    xTaskCreate(status_task, "csi_status", 4096, NULL, 4, NULL);
}
