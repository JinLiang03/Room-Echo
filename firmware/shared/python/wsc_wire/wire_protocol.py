"""Reference encoder/decoder for the WiFi Spatial Council wire protocol.

Package: ``wsc_wire``. Import as ``from wsc_wire.wire_protocol import ...``.

This module is a byte-for-byte port of ``firmware/shared/wire_protocol.c``.
The golden test compiles the C encoder on the host and compares its output
with this module's output; never change one without the other.

Layout: little-endian everywhere. See ``docs/WIRE_PROTOCOL.md``.
"""

from __future__ import annotations

import struct
import zlib
from dataclasses import dataclass, field

MAGIC_U32 = 0x57434652
PROTOCOL_VERSION = 1
FRAME_TYPE_DATA = 0x01
FRAME_TYPE_STATUS = 0x02
HEADER_LEN = 46
CSI_MAX_LEN = 1024
STATUS_PAYLOAD_LEN = 36
FRAME_MAX_LEN = HEADER_LEN + CSI_MAX_LEN + 4

TX_PAYLOAD_MAGIC = 0x58435357
TX_PAYLOAD_LEN = 24

PHY_FLAG_HT40 = 0x01
PHY_FLAG_SIG_MODE_HT = 0x02
PHY_FLAG_STBC = 0x04
PHY_FLAG_AGGREGATION = 0x08
PHY_FLAG_SGI = 0x10
PHY_FLAG_SMOOTHING = 0x20
PHY_FLAG_NOT_SOUNDING = 0x40

_HEADER_STRUCT = struct.Struct("<IBBHHIQIQBBhhBBHH")
_STATUS_STRUCT = struct.Struct("<7I2h4B")
_TX_PAYLOAD_STRUCT = struct.Struct("<IBBHIIQ")
_MAGIC_BYTES = struct.pack("<I", MAGIC_U32)


@dataclass(frozen=True)
class WireHeader:
    """Decoded fixed header (46 bytes)."""

    magic: int
    version: int
    frame_type: int
    header_len: int
    payload_len: int
    seq: int
    device_ts_us: int
    rx_id: int
    tx_id_hash: int
    channel: int
    bandwidth_mhz: int
    rssi_dbm_x100: int
    noise_floor_dbm_x100: int
    phy_flags: int
    first_word_invalid: int
    csi_len: int
    reserved: int

    @classmethod
    def from_bytes(cls, data: bytes) -> WireHeader:
        values = _HEADER_STRUCT.unpack(data)
        return cls(*values)


@dataclass(frozen=True)
class ParsedFrame:
    header: WireHeader
    payload: bytes

    @property
    def csi_bytes(self) -> bytes:
        if self.header.frame_type != FRAME_TYPE_DATA:
            raise ValueError("status frames have no CSI payload")
        return self.payload


@dataclass(frozen=True)
class StatusPayload:
    uptime_s: int
    free_heap: int
    counter_received: int
    counter_filtered: int
    counter_ring_overflow: int
    counter_serial_drop: int
    counter_bad_length: int
    last_rssi_dbm_x100: int
    last_noise_floor_dbm_x100: int


def encode_header(header: WireHeader) -> bytes:
    if header.magic != MAGIC_U32:
        raise ValueError("bad magic")
    if header.version != PROTOCOL_VERSION:
        raise ValueError(f"unsupported version {header.version}")
    if header.header_len != HEADER_LEN:
        raise ValueError(f"header_len must be {HEADER_LEN}")
    if header.bandwidth_mhz not in (20, 40):
        raise ValueError(f"invalid bandwidth {header.bandwidth_mhz}")
    return _HEADER_STRUCT.pack(
        header.magic,
        header.version,
        header.frame_type,
        header.header_len,
        header.payload_len,
        header.seq,
        header.device_ts_us,
        header.rx_id,
        header.tx_id_hash,
        header.channel,
        header.bandwidth_mhz,
        header.rssi_dbm_x100,
        header.noise_floor_dbm_x100,
        header.phy_flags,
        header.first_word_invalid,
        header.csi_len,
        header.reserved,
    )


def encode_data_frame(header: WireHeader, csi_bytes: bytes) -> bytes:
    if header.frame_type != FRAME_TYPE_DATA:
        raise ValueError("frame_type must be FRAME_TYPE_DATA")
    if header.payload_len != header.csi_len:
        raise ValueError("payload_len must equal csi_len for data frames")
    if header.csi_len != len(csi_bytes):
        raise ValueError("csi_len must equal len(csi_bytes)")
    if header.csi_len > CSI_MAX_LEN:
        raise ValueError(f"csi_len exceeds CSI_MAX_LEN={CSI_MAX_LEN}")
    frame = encode_header(header) + csi_bytes
    frame += struct.pack("<I", crc32(frame))
    return frame


def encode_status_frame(header: WireHeader, status: StatusPayload) -> bytes:
    if header.frame_type != FRAME_TYPE_STATUS:
        raise ValueError("frame_type must be FRAME_TYPE_STATUS")
    if header.payload_len != STATUS_PAYLOAD_LEN or header.csi_len != 0:
        raise ValueError("status frames require payload_len=STATUS_PAYLOAD_LEN, csi_len=0")
    payload = _STATUS_STRUCT.pack(
        status.uptime_s,
        status.free_heap,
        status.counter_received,
        status.counter_filtered,
        status.counter_ring_overflow,
        status.counter_serial_drop,
        status.counter_bad_length,
        status.last_rssi_dbm_x100,
        status.last_noise_floor_dbm_x100,
        0,
        0,
        0,
        0,
    )
    frame = encode_header(header) + payload
    frame += struct.pack("<I", crc32(frame))
    return frame


def encode_tx_payload(tx_id: int, seq: int, tx_ts_us: int) -> bytes:
    return _TX_PAYLOAD_STRUCT.pack(
        TX_PAYLOAD_MAGIC,
        PROTOCOL_VERSION,
        0,
        TX_PAYLOAD_LEN,
        tx_id,
        seq,
        tx_ts_us,
    )


def parse_tx_payload(data: bytes) -> tuple[int, int, int]:
    """Return (tx_id, seq, tx_ts_us) or raise ValueError."""
    if len(data) < TX_PAYLOAD_LEN:
        raise ValueError("truncated TX payload")
    magic, version, _reserved, payload_len, tx_id, seq, tx_ts_us = (
        _TX_PAYLOAD_STRUCT.unpack(data[:TX_PAYLOAD_LEN])
    )
    if magic != TX_PAYLOAD_MAGIC:
        raise ValueError("bad TX payload magic")
    if version != PROTOCOL_VERSION:
        raise ValueError(f"unsupported TX payload version {version}")
    if payload_len != TX_PAYLOAD_LEN:
        raise ValueError(f"TX payload len must be {TX_PAYLOAD_LEN}")
    return tx_id, seq, tx_ts_us


def crc32(data: bytes) -> int:
    """CRC-32 (IEEE 802.3), identical to ``wsc_crc32`` in C."""
    return zlib.crc32(data) & 0xFFFFFFFF


def seq_gap(prev: int, curr: int) -> int:
    """Signed (curr - prev) with uint32 wrap; defined for |gap| < 2**31."""
    diff = (curr - prev) & 0xFFFFFFFF
    return diff - 0x100000000 if diff >= 0x80000000 else diff


@dataclass
class FrameParser:
    """Streaming parser with magic resynchronization.

    Feed bytes in any chunking; complete frames are returned in order.
    Rejected bytes increment the corresponding rejection counters.
    """

    max_csi_len: int = CSI_MAX_LEN
    _buffer: bytearray = field(default_factory=bytearray)
    bad_magic: int = 0
    bad_version: int = 0
    bad_type: int = 0
    bad_length: int = 0
    bad_crc: int = 0

    def feed(self, data: bytes) -> list[ParsedFrame]:
        self._buffer.extend(data)
        frames: list[ParsedFrame] = []
        while True:
            idx = self._buffer.find(_MAGIC_BYTES)
            if idx < 0:
                # Keep only enough bytes to recognize a split magic.
                del self._buffer[: max(0, len(self._buffer) - 3)]
                return frames
            if idx > 0:
                self.bad_magic += 1
                del self._buffer[:idx]
            if len(self._buffer) < HEADER_LEN:
                return frames
            header = WireHeader.from_bytes(bytes(self._buffer[:HEADER_LEN]))
            if header.version != PROTOCOL_VERSION:
                self.bad_version += 1
                del self._buffer[:1]
                continue
            if header.header_len != HEADER_LEN or header.frame_type not in (
                FRAME_TYPE_DATA,
                FRAME_TYPE_STATUS,
            ):
                self.bad_type += 1
                del self._buffer[:1]
                continue
            if header.payload_len > self.max_csi_len:
                self.bad_length += 1
                del self._buffer[:1]
                continue
            total = HEADER_LEN + header.payload_len + 4
            if len(self._buffer) < total:
                return frames
            frame_bytes = bytes(self._buffer[:total])
            stored_crc = struct.unpack("<I", frame_bytes[-4:])[0]
            if stored_crc != crc32(frame_bytes[:-4]):
                self.bad_crc += 1
                del self._buffer[:1]
                continue
            frames.append(
                ParsedFrame(
                    header=header,
                    payload=frame_bytes[HEADER_LEN : HEADER_LEN + header.payload_len],
                )
            )
            del self._buffer[:total]


def parse_status_payload(payload: bytes) -> StatusPayload:
    if len(payload) < STATUS_PAYLOAD_LEN:
        raise ValueError("truncated status payload")
    values = _STATUS_STRUCT.unpack(payload[:STATUS_PAYLOAD_LEN])
    return StatusPayload(*values[:9])
