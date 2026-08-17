"""Replay bundle manifest, loading, and security verification."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Literal

import zstandard as zstd
from pydantic import BaseModel, ConfigDict, Field, ValidationError
from wifi_contracts import HASH_PATTERN, SourceMode

from .deident import safe_basename

MANIFEST_FILE = "manifest.json"
RAW_FILE = "raw.csi.zst"
EVENTS_FILE = "events.jsonl"
CHECKSUMS_FILE = "checksums.sha256"
DEFAULT_MAX_RAW_BYTES = 512 * 1024 * 1024


class ReplayManifest(BaseModel):
    """Versioned replay bundle manifest (see DATA_CONTRACTS §10)."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["replay-manifest.v1"] = "replay-manifest.v1"
    recording_id: str = Field(min_length=1)
    session_id: str = Field(min_length=1)
    created_at: datetime
    source_mode: SourceMode
    firmware_version: str = Field(min_length=1)
    collector_version: str = Field(min_length=1)
    contracts_version: str = Field(min_length=1)
    features_version: str | None = None
    estimator_version: str | None = None
    board_hashes: dict[str, str]
    topology_hash: str = Field(pattern=HASH_PATTERN)
    calibration_profile_id: str | None = None
    channel: int = Field(ge=1, le=196)
    bandwidth_mhz: Literal[20, 40]
    files: list[str]
    ground_truth_present: bool = False
    privacy: str = Field(min_length=1)
    status: Literal["complete", "incomplete"]


class VerifyResult(BaseModel):
    ok: bool
    errors: list[str] = Field(default_factory=list)
    manifest: ReplayManifest | None = None
    raw_bytes: int = 0


def _read_checksums(root: Path) -> dict[str, str]:
    lines = (root / CHECKSUMS_FILE).read_text(encoding="utf-8").splitlines()
    result: dict[str, str] = {}
    for line in lines:
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split()
        if len(parts) != 2:
            raise ValueError(f"malformed checksum line: {line!r}")
        result[parts[1]] = parts[0]
    return result


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _safe_resolved(root: Path, name: str) -> Path:
    safe_basename(name)
    candidate = (root / name).resolve()
    if not candidate.is_relative_to(root.resolve()):
        raise ValueError(f"path escapes bundle root: {name!r}")
    return candidate


class BundleVerifier:
    def __init__(
        self,
        bundle_root: Path,
        *,
        max_raw_bytes: int = DEFAULT_MAX_RAW_BYTES,
        require_complete: bool = True,
    ) -> None:
        self.bundle_root = Path(bundle_root)
        self.max_raw_bytes = max_raw_bytes
        self.require_complete = require_complete

    def verify(self) -> VerifyResult:
        errors: list[str] = []
        manifest: ReplayManifest | None = None
        raw_bytes = 0

        root = self.bundle_root
        if not root.is_dir():
            return VerifyResult(ok=False, errors=[f"not a directory: {root}"])

        try:
            manifest_data = json.loads(
                (root / MANIFEST_FILE).read_text(encoding="utf-8")
            )
            manifest = ReplayManifest.model_validate(manifest_data)
        except (OSError, json.JSONDecodeError, ValidationError) as exc:
            return VerifyResult(
                ok=False,
                errors=[f"invalid manifest: {exc}"],
            )

        if self.require_complete and manifest.status != "complete":
            errors.append(
                f"bundle status is {manifest.status!r}, not 'complete'"
            )

        for name in manifest.files:
            try:
                path = _safe_resolved(root, name)
                if not path.is_file():
                    errors.append(f"missing file: {name}")
            except ValueError as exc:
                errors.append(str(exc))

        try:
            checksums = _read_checksums(root)
        except (OSError, ValueError) as exc:
            errors.append(f"invalid checksums file: {exc}")
            checksums = {}

        for name in manifest.files:
            try:
                path = _safe_resolved(root, name)
                if path.is_file() and name in checksums:
                    if _sha256(path) != checksums[name]:
                        errors.append(f"checksum mismatch: {name}")
                elif path.is_file():
                    errors.append(f"no checksum entry for {name}")
            except ValueError:
                pass  # already reported above

        raw_path = root / RAW_FILE
        try:
            raw_bytes = self._decompressed_size(raw_path)
            if raw_bytes > self.max_raw_bytes:
                errors.append(
                    f"raw.csi.zst decompresses to {raw_bytes} bytes "
                    f"(cap {self.max_raw_bytes})"
                )
        except (OSError, zstd.ZstdError) as exc:
            errors.append(f"raw.csi.zst unreadable: {exc}")

        return VerifyResult(
            ok=not errors,
            errors=errors,
            manifest=manifest,
            raw_bytes=raw_bytes,
        )

    def _decompressed_size(self, path: Path) -> int:
        total = 0
        reader = zstd.ZstdDecompressor().stream_reader(
            path.open("rb"), read_across_frames=True
        )
        with reader:
            while True:
                chunk = reader.read(1 << 20)
                if not chunk:
                    break
                total += len(chunk)
                if total > self.max_raw_bytes:
                    break
        return total
