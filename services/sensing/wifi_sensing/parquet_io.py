"""FeatureWindow Parquet writer/reader with schema versioning."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import polars as pl
from pydantic import ValidationError
from wifi_contracts import FeatureWindow

SCHEMA_VERSION = "1.0.0"
META_FILE = "features.meta.json"


def windows_to_parquet(
    windows: list[FeatureWindow],
    path: Path,
    *,
    source: str,
    extra: dict[str, Any] | None = None,
) -> Path:
    """Write windows as one parquet file plus a versioned meta sidecar."""
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = [window.model_dump(mode="json") for window in windows]
    df = pl.DataFrame(rows)
    df.write_parquet(path)
    meta = {
        "schema_version": SCHEMA_VERSION,
        "source": source,
        "window_count": len(windows),
        "written_at": datetime.now(UTC).isoformat(),
        **(extra or {}),
    }
    (path.parent / META_FILE).write_text(
        json.dumps(meta, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return path


def parquet_to_windows(path: Path) -> list[FeatureWindow]:
    """Read a parquet written by windows_to_parquet and validate it."""
    meta_path = path.parent / META_FILE
    if not meta_path.is_file():
        raise ValueError(f"missing feature meta sidecar: {meta_path}")
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    if meta.get("schema_version") != SCHEMA_VERSION:
        raise ValueError(
            f"unsupported feature schema {meta.get('schema_version')!r}"
        )
    df = pl.read_parquet(path)
    windows: list[FeatureWindow] = []
    for row in df.to_dicts():
        try:
            windows.append(FeatureWindow.model_validate(row))
        except ValidationError as exc:
            raise ValueError(f"invalid feature row: {exc}") from exc
    if len(windows) != int(meta.get("window_count", -1)):
        raise ValueError(
            f"window count mismatch: {len(windows)} rows vs meta {meta.get('window_count')}"
        )
    return windows
