idf_component_register(
    SRCS "crc32.c" "wire_protocol.c" "frame_pool.c"
    INCLUDE_DIRS "include"
)

target_compile_options(${COMPONENT_LIB} PRIVATE -Wall -Wextra -Werror)
