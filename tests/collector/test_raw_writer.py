"""RawBundleWriter: atomic publish, checksums, incomplete marker, no overwrite."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest
from wifi_collector.raw_writer import RawBundleWriter
from wifi_collector.replay_bundle import (
    CHECKSUMS_FILE,
    EVENTS_FILE,
    MANIFEST_FILE,
    RAW_FILE,
    BundleVerifier,
    ReplayManifest,
)


def _manifest(session_id: str, root: Path) -> ReplayManifest:
    return ReplayManifest(
        schema_version="replay-manifest.v1",
        recording_id=session_id,
        session_id=session_id,
        created_at=datetime(2026, 8, 6, tzinfo=UTC),
        source_mode="mock",
        firmware_version="0.0.0-mock",
        collector_version="0.1.0",
        contracts_version="1.0.0",
        board_hashes={"rx-a": "sha256:" + "a" * 64, "rx-b": "sha256:" + "b" * 64},
        topology_hash="sha256:" + "c" * 64,
        channel=6,
        bandwidth_mhz=20,
        files=[],
        privacy="test",
        status="incomplete",
    )


def test_finalize_publishes_complete_bundle(tmp_path: Path) -> None:
    writer = RawBundleWriter(
        session_id="sess-1",
        raw_root=tmp_path,
        manifest=_manifest("sess-1", tmp_path),
    )
    writer.start()
    writer.append_wire_frame(b"WCFR" + b"\x00" * 30)
    writer.append_event("session.started", {"a": 1})
    final = writer.finalize()
    assert final == tmp_path / "sess-1"
    assert (final / RAW_FILE).is_file()
    assert (final / EVENTS_FILE).is_file()
    assert (final / MANIFEST_FILE).is_file()
    assert (final / CHECKSUMS_FILE).is_file()
    assert not list(tmp_path.glob(".tmp-*"))
    result = BundleVerifier(final).verify()
    assert result.ok, result.errors
    assert result.manifest is not None
    assert result.manifest.status == "complete"


def test_abort_publishes_incomplete_marker(tmp_path: Path) -> None:
    writer = RawBundleWriter(
        session_id="sess-2",
        raw_root=tmp_path,
        manifest=_manifest("sess-2", tmp_path),
    )
    writer.start()
    writer.append_wire_frame(b"WCFR" + b"\x00" * 30)
    final = writer.abort(reason="disk error")
    assert (final / "INCOMPLETE").is_file()
    result = BundleVerifier(final, require_complete=True).verify()
    assert not result.ok
    assert any("not 'complete'" in error for error in result.errors)
    result = BundleVerifier(final, require_complete=False).verify()
    assert result.ok


def test_refuses_to_overwrite_existing_bundle(tmp_path: Path) -> None:
    writer = RawBundleWriter(
        session_id="sess-3",
        raw_root=tmp_path,
        manifest=_manifest("sess-3", tmp_path),
    )
    writer.start()
    writer.finalize()
    second = RawBundleWriter(
        session_id="sess-3",
        raw_root=tmp_path,
        manifest=_manifest("sess-3", tmp_path),
    )
    with pytest.raises(FileExistsError):
        second.start()
