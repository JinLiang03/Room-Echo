"""Fixed inputs shared by the C golden test and the Python reference."""

from __future__ import annotations

from wsc_wire.wire_protocol import (
    FRAME_TYPE_DATA,
    FRAME_TYPE_STATUS,
    HEADER_LEN,
    MAGIC_U32,
    PROTOCOL_VERSION,
    STATUS_PAYLOAD_LEN,
    StatusPayload,
    WireHeader,
)

CSI_BYTES = bytes([0x00, 0x01, 0x02, 0x03, 0xFE, 0xFD, 0x7F, 0x80])

DATA_HEADER = WireHeader(
    magic=MAGIC_U32,
    version=PROTOCOL_VERSION,
    frame_type=FRAME_TYPE_DATA,
    header_len=HEADER_LEN,
    payload_len=len(CSI_BYTES),
    seq=0xDEADBEEF,
    device_ts_us=0x0102030405060708,
    rx_id=1,
    tx_id_hash=0x1122334455667788,
    channel=6,
    bandwidth_mhz=20,
    rssi_dbm_x100=-6500,
    noise_floor_dbm_x100=-9500,
    phy_flags=0x02,
    first_word_invalid=0,
    csi_len=len(CSI_BYTES),
    reserved=0,
)

STATUS_HEADER = WireHeader(
    magic=MAGIC_U32,
    version=PROTOCOL_VERSION,
    frame_type=FRAME_TYPE_STATUS,
    header_len=HEADER_LEN,
    payload_len=STATUS_PAYLOAD_LEN,
    seq=42,
    device_ts_us=0x0102030405060708,
    rx_id=1,
    tx_id_hash=0x1122334455667788,
    channel=6,
    bandwidth_mhz=20,
    rssi_dbm_x100=-6600,
    noise_floor_dbm_x100=-9400,
    phy_flags=0,
    first_word_invalid=0,
    csi_len=0,
    reserved=0,
)

STATUS_PAYLOAD = StatusPayload(
    uptime_s=42,
    free_heap=0x123456,
    counter_received=1000,
    counter_filtered=3,
    counter_ring_overflow=1,
    counter_serial_drop=2,
    counter_bad_length=0,
    last_rssi_dbm_x100=-6600,
    last_noise_floor_dbm_x100=-9400,
)

TX_PAYLOAD = (7, 0xF0F0F0F0, 0x0102030405060708)
