#!/usr/bin/env python3
"""Package a reproducible source archive with checksums + smoke test."""

from __future__ import annotations

import argparse
import hashlib
import py_compile
import subprocess
import tarfile
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VERSION = "0.1.0"
ARCHIVE_NAME = f"wifi-spatial-council-{VERSION}.tar.gz"

EXCLUDE_DIRS = {
    ".venv",
    "node_modules",
    "dist",
    "__pycache__",
    ".git",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    "test-results",
    "playwright-report",
    "artifacts",
}


def _include(path: Path) -> bool:
    rel = path.relative_to(ROOT)
    if any(part in EXCLUDE_DIRS for part in rel.parts):
        return False
    if (
        len(rel.parts) >= 3
        and rel.parts[0] == "firmware"
        and rel.parts[1] in ("csi_tx", "csi_rx")
        and rel.parts[2] == "build"
    ):
        return False
    if rel.parts[:2] == ("data", "derived"):
        return False
    if rel.parts[:2] == ("data", "raw"):
        return False
    if path.name == ".env" or (
        path.name.startswith(".env.") and path.name != ".env.example"
    ):
        return False
    return not (path.name.endswith(".pyc") or path.name == ".DS_Store")


def _candidate_files() -> list[Path]:
    """Package only Git-visible files, never ignored local state or secrets."""
    result = subprocess.run(
        [
            "git",
            "-C",
            str(ROOT),
            "ls-files",
            "-z",
            "--cached",
            "--others",
            "--exclude-standard",
        ],
        check=False,
        capture_output=True,
        text=True,
        timeout=30,
    )
    if result.returncode != 0:
        raise RuntimeError("release packaging requires a readable Git worktree")
    return [ROOT / item for item in result.stdout.split("\0") if item]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", default="artifacts/release", type=Path)
    args = parser.parse_args(argv)
    out = args.output
    out.mkdir(parents=True, exist_ok=True)
    archive = out / ARCHIVE_NAME

    with tarfile.open(archive, "w:gz") as tar:
        for path in sorted(_candidate_files()):
            if not path.is_file() or not _include(path):
                continue
            tar.add(path, arcname=Path("wifi-spatial-council") / path.relative_to(ROOT))

    checksum_path = out / f"{ARCHIVE_NAME}.sha256"
    checksum_path.write_text(f"{sha256(archive)}  {ARCHIVE_NAME}\n", encoding="utf-8")

    # Smoke: extract to a temp dir, verify checksum + structure + compile core.
    with tempfile.TemporaryDirectory() as tmp:
        extracted = Path(tmp) / "wifi-spatial-council"
        with tarfile.open(archive, "r:gz") as tar:
            tar.extractall(tmp)
        rehash = sha256(archive)
        expected = checksum_path.read_text(encoding="utf-8").split()[0]
        assert rehash == expected, "archive checksum mismatch after write"
        required = [
            "pyproject.toml",
            "uv.lock",
            "Makefile",
            "PROJECT_INDEX.yaml",
            "STATE.md",
            "apps/web/package.json",
            "firmware/build/manifest.json",
            "data/fixtures/demo_2min/manifest.json",
        ]
        missing = [name for name in required if not (extracted / name).is_file()]
        assert not missing, f"archive missing: {missing}"
        compiled = 0
        for path in (extracted / "packages" / "contracts").rglob("*.py"):
            py_compile.compile(str(path), doraise=True)
            compiled += 1
        print(f"smoke: archive structure ok, checksum ok, compiled {compiled} modules")

    size_mb = archive.stat().st_size / (1024 * 1024)
    print(f"archive: {archive} ({size_mb:.1f} MB)")
    print(f"checksum: {checksum_path.read_text(encoding='utf-8').strip()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
