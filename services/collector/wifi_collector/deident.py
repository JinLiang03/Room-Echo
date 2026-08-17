"""De-identification helpers: never persist real MACs or absolute port paths."""

from __future__ import annotations

import hashlib
import secrets
from pathlib import Path


def session_salt() -> bytes:
    """Per-session random salt for MAC hashing."""
    return secrets.token_bytes(16)


def hash_mac(mac_bytes: bytes, salt: bytes) -> str:
    """SHA-256(salt || mac) hex, prefixed for clarity."""
    digest = hashlib.sha256(salt + mac_bytes).hexdigest()
    return f"sha256:{digest}"


def safe_basename(path: str) -> str:
    """Return the basename of a path; rejects anything path-like."""
    name = Path(path).name
    if not name or name in (".", "..") or "/" in path or "\\" in path:
        raise ValueError(f"unsafe path in manifest: {path!r}")
    return name
