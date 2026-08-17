"""Conversion between wire-protocol frames and NormalizedCsiFrame.

The wire frame is the raw fact; NormalizedCsiFrame is the derived view.
Round-trips are byte-stable for fields carried by the wire protocol:
seq, device_ts_us, rx_id, tx_id_hash, channel, bandwidth, rssi, noise_floor,
csi_iq. Fields the wire does not carry (session_id, source_mode, host_ts_ns,
quality) are derived deterministically by the consumer.
"""

from __future__ import annotations

from typing import Literal, cast

from wifi_contracts import CsiQuality, NormalizedCsiFrame, SourceMode

from wsc_wire.wire_protocol import (
    FRAME_TYPE_DATA,
    HEADER_LEN,
    MAGIC_U32,
    PROTOCOL_VERSION,
    ParsedFrame,
    WireHeader,
    encode_data_frame,
)

LINK_TO_RX_ID = {"rx-a": 1, "rx-b": 2}
RX_ID_TO_LINK = {value: key for key, value in LINK_TO_RX_ID.items()}

_FNV_OFFSET = 0xCBF29CE484222325
_FNV_PRIME = 0x100000001B3


def _fnv1a64(data: bytes) -> int:
    value = _FNV_OFFSET
    for byte in data:
        value ^= byte
        value = (value * _FNV_PRIME) & 0xFFFFFFFFFFFFFFFF
    return value


def tx_id_hash_to_u64(tx_id_hash: str | None) -> int:
    """Map a normalized tx_id_hash string to the wire's u64."""
    if tx_id_hash and tx_id_hash.startswith("fnv1a64:"):
        suffix = tx_id_hash[len("fnv1a64:") :]
        if len(suffix) == 16:
            try:
                return int(suffix, 16)
            except ValueError:
                pass
    return _fnv1a64((tx_id_hash or "").encode("utf-8"))


def u64_to_tx_id_hash(value: int) -> str:
    return f"fnv1a64:{value & 0xFFFFFFFFFFFFFFFF:016x}"


def rx_id_to_link(rx_id: int) -> str:
    return RX_ID_TO_LINK.get(rx_id, f"rx-{rx_id}")


def link_to_rx_id(link_id: str) -> int:
    return LINK_TO_RX_ID.get(link_id, 0xFFFFFFFF & _fnv1a64(link_id.encode()))


def wire_bytes_from_normalized(frame: NormalizedCsiFrame) -> bytes:
    """Serialize a normalized frame to wire bytes (for raw recording)."""
    csi_bytes = bytes((value & 0xFF) for value in frame.csi_iq)
    header = WireHeader(
        magic=MAGIC_U32,
        version=PROTOCOL_VERSION,
        frame_type=FRAME_TYPE_DATA,
        header_len=HEADER_LEN,
        payload_len=len(csi_bytes),
        seq=frame.seq,
        device_ts_us=frame.device_ts_us,
        rx_id=link_to_rx_id(frame.link_id),
        tx_id_hash=tx_id_hash_to_u64(frame.tx_id_hash),
        channel=frame.channel,
        bandwidth_mhz=frame.bandwidth_mhz,
        rssi_dbm_x100=round(frame.rssi_dbm * 100),
        noise_floor_dbm_x100=round(frame.noise_floor_dbm * 100),
        phy_flags=0,
        first_word_invalid=0,
        csi_len=len(csi_bytes),
        reserved=0,
    )
    return encode_data_frame(header, csi_bytes)


def normalized_from_wire_frame(
    parsed: ParsedFrame,
    *,
    session_id: str,
    source_mode: SourceMode,
) -> NormalizedCsiFrame:
    """Convert one parsed wire data frame into a normalized frame."""
    header = parsed.header
    csi_iq = [
        value - 256 if value >= 128 else value for value in parsed.payload
    ]
    return NormalizedCsiFrame(
        schema_version="1.0.0",
        session_id=session_id,
        source_mode=source_mode,
        link_id=rx_id_to_link(header.rx_id),
        rx_id=rx_id_to_link(header.rx_id),
        tx_id_hash=u64_to_tx_id_hash(header.tx_id_hash),
        seq=header.seq,
        device_ts_us=header.device_ts_us,
        # The wire carries the TX clock; the host clock is derived for
        # deterministic replay (live paths may stamp a real host clock later).
        host_ts_ns=header.device_ts_us * 1000,
        channel=header.channel,
        bandwidth_mhz=cast(Literal[20, 40], header.bandwidth_mhz),
        rssi_dbm=header.rssi_dbm_x100 / 100.0,
        noise_floor_dbm=header.noise_floor_dbm_x100 / 100.0,
        rate=None,
        secondary_channel=None,
        ltf_mode=None,
        first_word_invalid=header.first_word_invalid != 0,
        csi_iq=csi_iq,
        quality=CsiQuality(
            parse_ok=True,
            sequence_gap=0,
            timestamp_monotonic=True,
            notes=[],
        ),
    )
