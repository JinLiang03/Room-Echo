"""Streaming parser: resync, rejection classes, wrap, and length limits."""

from __future__ import annotations

import pytest
from golden_case import (
    CSI_BYTES,
    DATA_HEADER,
    STATUS_HEADER,
    STATUS_PAYLOAD,
    TX_PAYLOAD,
)

from wsc_wire.wire_protocol import (
    CSI_MAX_LEN,
    HEADER_LEN,
    PROTOCOL_VERSION,
    FrameParser,
    ParsedFrame,
    encode_data_frame,
    encode_header,
    encode_status_frame,
    encode_tx_payload,
    parse_status_payload,
    parse_tx_payload,
    seq_gap,
)


def test_round_trip_data_frame() -> None:
    frame = encode_data_frame(DATA_HEADER, CSI_BYTES)
    parsed = FrameParser().feed(frame)
    assert len(parsed) == 1
    item = parsed[0]
    assert item.header == DATA_HEADER
    assert item.csi_bytes == CSI_BYTES


def test_round_trip_status_frame() -> None:
    frame = encode_status_frame(STATUS_HEADER, STATUS_PAYLOAD)
    parsed = FrameParser().feed(frame)
    assert len(parsed) == 1
    status = parse_status_payload(parsed[0].payload)
    assert status.uptime_s == 42
    assert status.counter_ring_overflow == 1


def test_byte_at_a_time_chunking() -> None:
    frame = encode_data_frame(DATA_HEADER, CSI_BYTES)
    parser = FrameParser()
    parsed: list[ParsedFrame] = []
    for byte in frame:
        parsed.extend(parser.feed(bytes([byte])))
    assert len(parsed) == 1
    assert parsed[0].header == DATA_HEADER


def test_bad_crc_rejected_and_stream_recovers() -> None:
    good = encode_data_frame(DATA_HEADER, CSI_BYTES)
    corrupt = bytearray(good)
    corrupt[20] ^= 0xFF  # inside header, breaks CRC
    stream = bytes(corrupt) + good
    parser = FrameParser()
    parsed = parser.feed(stream)
    assert len(parsed) == 1  # the good frame recovered
    assert parsed[0].header == DATA_HEADER
    assert parser.bad_crc == 1


def test_truncated_frame_buffered_then_completed() -> None:
    frame = encode_data_frame(DATA_HEADER, CSI_BYTES)
    parser = FrameParser()
    assert parser.feed(frame[: HEADER_LEN + 3]) == []
    assert parser.feed(frame[HEADER_LEN + 3 :])[0].header == DATA_HEADER


def test_oversize_payload_rejected() -> None:
    from dataclasses import replace

    header = replace(
        DATA_HEADER,
        payload_len=CSI_MAX_LEN + 1,
        csi_len=CSI_MAX_LEN + 1,
    )
    # Build raw header + dummy payload; CRC is irrelevant because the parser
    # rejects on length before checking the CRC.
    frame = encode_header(header) + bytes(CSI_MAX_LEN + 1) + b"\x00\x00\x00\x00"
    parser = FrameParser()
    assert parser.feed(frame) == []
    assert parser.bad_length == 1


def test_unknown_version_rejected() -> None:
    frame = bytearray(encode_data_frame(DATA_HEADER, CSI_BYTES))
    frame[4] = PROTOCOL_VERSION + 1
    parser = FrameParser()
    assert parser.feed(bytes(frame)) == []
    assert parser.bad_version == 1


def test_noise_bytes_before_frame_resync() -> None:
    noise = b"\x00\x01\x02not-a-frame\xff\xfe"
    frame = encode_data_frame(DATA_HEADER, CSI_BYTES)
    parser = FrameParser()
    parsed = parser.feed(noise + frame)
    assert len(parsed) == 1
    assert parsed[0].header == DATA_HEADER
    assert parser.bad_magic >= 1


def test_wrong_magic_rejected_and_skipped() -> None:
    bogus = b"\x00\x00\x00\x00" + bytes(HEADER_LEN - 4)
    frame = encode_data_frame(DATA_HEADER, CSI_BYTES)
    parser = FrameParser()
    parsed = parser.feed(bogus + frame)
    assert len(parsed) == 1
    assert parser.bad_magic >= 1


def test_sequence_wrap_defined() -> None:
    assert seq_gap(0xFFFFFFFF, 2) == 3
    assert seq_gap(2, 0xFFFFFFFF) == -3
    assert seq_gap(5, 5) == 0
    assert seq_gap(100, 104) == 4


def test_tx_payload_round_trip_and_rejection() -> None:
    tx_id, seq, ts = TX_PAYLOAD
    data = encode_tx_payload(tx_id, seq, ts)
    assert parse_tx_payload(data) == TX_PAYLOAD
    with pytest.raises(ValueError, match="magic"):
        parse_tx_payload(b"\x00" * 24)
    with pytest.raises(ValueError, match="truncated"):
        parse_tx_payload(data[:10])


def test_length_limits_on_encode() -> None:
    from dataclasses import replace

    big_header = replace(
        DATA_HEADER,
        payload_len=CSI_MAX_LEN + 1,
        csi_len=CSI_MAX_LEN + 1,
    )
    with pytest.raises(ValueError, match="CSI_MAX_LEN"):
        encode_data_frame(big_header, bytes(CSI_MAX_LEN + 1))
    with pytest.raises(ValueError, match="csi_len"):
        encode_data_frame(DATA_HEADER, bytes(2))
