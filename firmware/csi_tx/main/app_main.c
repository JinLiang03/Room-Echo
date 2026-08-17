/*
 * WiFi Spatial Council — dedicated CSI transmitter.
 *
 * Sends fixed-rate ESP-NOW broadcast frames on a fixed channel/bandwidth with
 * power save disabled. The payload carries protocol version, TX ID, a
 * uint32 sequence, and a TX timestamp so receivers can pair frames and the
 * host can detect gaps.
 *
 * Based on the Espressif esp-csi get-started example (commit
 * 8633d67152db2808f141cc1595970aa9cf406045), reworked for fixed HT20,
 * configurable channel/rate, and the shared wire protocol.
 *
 * SPDX-License-Identifier: Apache-2.0
 */

#include <inttypes.h>
#include <stdio.h>
#include <string.h>

#include "esp_event.h"
#include "esp_log.h"
#include "esp_mac.h"
#include "esp_netif.h"
#include "esp_now.h"
#include "esp_timer.h"
#include "esp_wifi.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "nvs_flash.h"
#include "wire_protocol.h"

#define WSC_TAG "csi_tx"

static const uint8_t s_tx_mac[6] = {
    CONFIG_WSC_TX_MAC_0,
    CONFIG_WSC_TX_MAC_1,
    CONFIG_WSC_TX_MAC_2,
    CONFIG_WSC_TX_MAC_3,
    CONFIG_WSC_TX_MAC_4,
    CONFIG_WSC_TX_MAC_5,
};

static const uint8_t s_broadcast_mac[6] = {0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF};

static uint32_t s_tx_errors = 0;

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
        esp_wifi_set_channel(CONFIG_WSC_TX_CHANNEL, WIFI_SECOND_CHAN_NONE));
    ESP_ERROR_CHECK(esp_wifi_set_mac(WIFI_IF_STA, s_tx_mac));
}

static void esp_now_init_broadcast(void)
{
    ESP_ERROR_CHECK(esp_now_init());

    esp_now_peer_info_t peer = {
        .channel = CONFIG_WSC_TX_CHANNEL,
        .ifidx = WIFI_IF_STA,
        .encrypt = false,
    };
    memcpy(peer.peer_addr, s_broadcast_mac, sizeof(peer.peer_addr));
    ESP_ERROR_CHECK(esp_now_add_peer(&peer));

    esp_now_rate_config_t rate_config = {
        .phymode = WIFI_PHY_MODE_HT20,
        .rate = WIFI_PHY_RATE_MCS0_LGI,
        .ersu = false,
        .dcm = false,
    };
    ESP_ERROR_CHECK(esp_now_set_peer_rate_config(peer.peer_addr, &rate_config));
}

static void tx_task(void *arg)
{
    (void)arg;
    uint32_t seq = 0;
    uint8_t payload[WSC_TX_PAYLOAD_LEN];
    const TickType_t period = pdMS_TO_TICKS(1000 / CONFIG_WSC_TX_RATE_HZ);
    TickType_t last_log = xTaskGetTickCount();

    for (;;) {
        size_t len = 0;
        const uint64_t tx_ts_us = esp_timer_get_time();
        if (!wsc_encode_tx_payload(payload, sizeof(payload), &len,
                                   CONFIG_WSC_TX_ID, seq, tx_ts_us)) {
            ESP_LOGE(WSC_TAG, "TX payload encode failed");
            seq++;
            vTaskDelay(period);
            continue;
        }
        const esp_err_t err = esp_now_send(s_broadcast_mac, payload, len);
        if (err != ESP_OK) {
            s_tx_errors++;
        }
        seq++; /* uint32 wrap-around is defined (modulo 2^32) */

        if ((xTaskGetTickCount() - last_log) >= pdMS_TO_TICKS(10000)) {
            last_log = xTaskGetTickCount();
            ESP_LOGI(WSC_TAG,
                     "rate_hz=%d seq=%" PRIu32 " errors=%" PRIu32
                     " heap=%" PRIu32,
                     CONFIG_WSC_TX_RATE_HZ, seq, s_tx_errors,
                     (uint32_t)esp_get_free_heap_size());
        }
        vTaskDelay(period);
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

    wifi_init();
    esp_now_init_broadcast();

    xTaskCreate(tx_task, "csi_tx", 4096, NULL, 5, NULL);
}
