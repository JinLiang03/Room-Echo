idf_component_register(
    SRCS "app_main.c"
    INCLUDE_DIRS "."
    REQUIRES nvs_flash esp_wifi esp_netif esp_event esp_timer driver shared
)

target_compile_options(${COMPONENT_LIB} PRIVATE -Wall -Wextra -Werror)
