"""C encoder (compiled on the host) must match the Python reference byte-for-byte."""

from __future__ import annotations

from pathlib import Path

from golden_case import (
    CSI_BYTES,
    DATA_HEADER,
    STATUS_HEADER,
    STATUS_PAYLOAD,
    TX_PAYLOAD,
)

from wsc_wire.wire_protocol import (
    encode_data_frame,
    encode_status_frame,
    encode_tx_payload,
)

ROOT = Path(__file__).resolve().parents[2]
GOLDEN_DIR = ROOT / "tests" / "firmware_contract" / "golden"


def _c_hex(stdout: str, label: str) -> bytes:
    for line in stdout.splitlines():
        if line.startswith(f"{label}:"):
            return bytes.fromhex(line.split(":", 1)[1])
    raise AssertionError(f"missing {label} in C golden output:\n{stdout}")


def test_data_frame_matches_c(wire_golden_stdout: str) -> None:
    expected = encode_data_frame(DATA_HEADER, CSI_BYTES)
    assert _c_hex(wire_golden_stdout, "data_frame") == expected


def test_status_frame_matches_c(wire_golden_stdout: str) -> None:
    expected = encode_status_frame(STATUS_HEADER, STATUS_PAYLOAD)
    assert _c_hex(wire_golden_stdout, "status_frame") == expected


def test_tx_payload_matches_c(wire_golden_stdout: str) -> None:
    tx_id, seq, ts = TX_PAYLOAD
    expected = encode_tx_payload(tx_id, seq, ts)
    assert _c_hex(wire_golden_stdout, "tx_payload") == expected


def test_checked_in_golden_file_is_current() -> None:
    golden = GOLDEN_DIR / "data_frame_golden.hex"
    assert golden.is_file(), "golden file missing; regenerate it"
    expected = encode_data_frame(DATA_HEADER, CSI_BYTES)
    assert golden.read_text(encoding="ascii").strip() == expected.hex()


def test_c_data_frame_matches_checked_in_golden(wire_golden_stdout: str) -> None:
    golden = (GOLDEN_DIR / "data_frame_golden.hex").read_text(
        encoding="ascii"
    ).strip()
    assert _c_hex(wire_golden_stdout, "data_frame").hex() == golden


def test_c_crc_known_answer_via_exit_code(wire_golden_stdout: str) -> None:
    # The C program exits non-zero if crc32("123456789") != 0xCBF43926;
    # reaching this point means the known-answer test passed.
    assert "data_frame:" in wire_golden_stdout


def test_frame_pool_c_host_test(frame_pool_ok: bool) -> None:
    assert frame_pool_ok
