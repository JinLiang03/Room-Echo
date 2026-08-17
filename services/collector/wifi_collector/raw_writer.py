"""Append-only raw bundle writer with atomic publish and checksums."""

from __future__ import annotations

import hashlib
import json
import os
import uuid
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, BinaryIO, Literal

import zstandard as zstd

from .replay_bundle import (
    CHECKSUMS_FILE,
    EVENTS_FILE,
    MANIFEST_FILE,
    RAW_FILE,
    ReplayManifest,
)


def _fsync_file(handle: Any) -> None:
    handle.flush()
    os.fsync(handle.fileno())


def _fsync_dir(path: Path) -> None:
    fd = os.open(path, os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


class RawBundleWriter:
    """Writes a replay bundle to a temp dir, then atomically publishes it.

    The temp bundle is never visible under the final name until finalize()
    succeeds. abort() publishes the bundle marked ``incomplete`` with an
    INCOMPLETE marker so an interrupted recording is detectable, never
    mistaken for a complete bundle.
    """

    def __init__(
        self,
        *,
        session_id: str,
        raw_root: Path,
        manifest: ReplayManifest,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self.session_id = session_id
        self.raw_root = Path(raw_root)
        self.manifest = manifest
        self.final_dir = self.raw_root / session_id
        self.tmp_dir = self.raw_root / f".tmp-{session_id}-{uuid.uuid4().hex[:8]}"
        self._raw_handle: BinaryIO | None = None
        self._events_handle: BinaryIO | None = None
        self._zstd_writer: Any = None
        self._started = False
        self._clock = clock or (lambda: datetime.now(UTC))

    def start(self) -> None:
        if self._started:
            raise RuntimeError("writer already started")
        if self.final_dir.exists():
            raise FileExistsError(f"bundle already exists: {self.final_dir}")
        self.raw_root.mkdir(parents=True, exist_ok=True)
        self.tmp_dir.mkdir(parents=True, exist_ok=False)
        raw_handle = (self.tmp_dir / RAW_FILE).open("wb")
        self._raw_handle = raw_handle
        self._zstd_writer = zstd.ZstdCompressor(level=3).stream_writer(
            raw_handle
        )
        self._events_handle = (self.tmp_dir / EVENTS_FILE).open("wb")
        self._started = True

    def append_wire_frame(self, data: bytes) -> None:
        self._require_started()
        assert self._zstd_writer is not None
        self._zstd_writer.write(data)

    def append_event(self, event_type: str, payload: dict[str, object]) -> None:
        self._require_started()
        assert self._events_handle is not None
        line = {
            "schema_version": "replay-event.v1",
            "session_id": self.session_id,
            "event_type": event_type,
            "emitted_at": self._clock().isoformat(),
            "payload": payload,
        }
        self._events_handle.write(
            (json.dumps(line, ensure_ascii=False, sort_keys=True) + "\n").encode(
                "utf-8"
            )
        )

    def finalize(
        self,
        status: Literal["complete", "incomplete"] = "complete",
    ) -> Path:
        """Close streams, write manifest + checksums, publish atomically."""
        self._require_started()
        assert self._zstd_writer is not None
        assert self._events_handle is not None
        assert self._raw_handle is not None

        # ZstdCompressor.stream_writer owns the wrapped file and closes it on
        # close(). Finish the frame before fsync so the durable bytes include
        # the frame footer rather than only the latest compressed block.
        self._zstd_writer.flush(zstd.FLUSH_FRAME)
        _fsync_file(self._raw_handle)
        self._zstd_writer.close()
        self._zstd_writer = None
        self._raw_handle = None
        _fsync_file(self._events_handle)
        self._events_handle.close()
        self._events_handle = None

        self.manifest.status = status
        files = [RAW_FILE, EVENTS_FILE]
        self.manifest.files = files
        self.manifest.recording_id = self.session_id

        checksum_lines = []
        for name in files:
            path = self.tmp_dir / name
            checksum_lines.append(f"{_sha256_file(path)}  {name}")
        with (self.tmp_dir / CHECKSUMS_FILE).open("w", encoding="utf-8") as handle:
            handle.write("\n".join(checksum_lines) + "\n")
            _fsync_file(handle)

        manifest_path = self.tmp_dir / MANIFEST_FILE
        with manifest_path.open("w", encoding="utf-8") as handle:
            handle.write(self.manifest.model_dump_json(indent=2) + "\n")
            _fsync_file(handle)

        if status == "incomplete":
            (self.tmp_dir / "INCOMPLETE").write_text(
                "recording interrupted; bundle is not complete\n",
                encoding="utf-8",
            )

        _fsync_dir(self.tmp_dir)
        os.rename(self.tmp_dir, self.final_dir)
        _fsync_dir(self.raw_root)
        self._started = False
        return self.final_dir

    def abort(self, reason: str) -> Path:
        """Publish the bundle marked incomplete (recoverable, inspectable)."""
        try:
            self.append_event(
                "session.aborted",
                {"reason": reason},
            )
            return self.finalize(status="incomplete")
        except Exception:
            # Best effort: leave the temp dir for manual recovery.
            if self._zstd_writer is not None:
                self._zstd_writer.close()
            if self._events_handle is not None:
                self._events_handle.close()
            raise

    def _require_started(self) -> None:
        if not self._started:
            raise RuntimeError("writer not started")
