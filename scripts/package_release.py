#!/usr/bin/env python3
"""Package a reproducible source archive with checksums + smoke test."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import io
import json
import py_compile
import re
import subprocess
import tarfile
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VERSION = "0.1.0"
RELEASE_MANIFEST_NAME = "RELEASE_MANIFEST.json"
ARCHIVE_ROOT = Path("wifi-spatial-council")
ZIP_TIMESTAMP = (1980, 1, 1, 0, 0, 0)
REQUIRED_RELEASE_PATHS = (
    "pyproject.toml",
    "uv.lock",
    "Makefile",
    "PROJECT_INDEX.yaml",
    "STATE.md",
    "Dockerfile",
    "render.yaml",
    "SUBMISSION_README.md",
    "apps/web/package.json",
    "apps/web/package-lock.json",
    "apps/web/src/main.tsx",
    "services/api/wifi_api/agent_routes.py",
    "services/api/wifi_api/mcp_server.py",
    "services/api/wifi_api/real_provider.py",
    "services/council/wifi_council/continuity.py",
    "services/council/wifi_council/deepseek.py",
    "scripts/mcp_smoke.py",
    "scripts/warm_render.py",
    "scripts/verify_openai_full_council.py",
    "firmware/build/manifest.json",
    "data/fixtures/demo_2min/manifest.json",
    RELEASE_MANIFEST_NAME,
)
ABSOLUTE_HOME_MARKERS = (b"/" + b"Users/", b"/" + b"home/")
SERIAL_DEVICE_PATTERN = re.compile(
    re.escape(b"/dev/" + b"cu.") + rb"([A-Za-z0-9._-]+)"
)
GENERIC_SERIAL_TOKEN = re.compile(
    r"(?:[XYZ]|(?:usbmodem|usbserial-?)[A-Z][A-Z0-9_-]*)\Z"
)

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
    if rel.parts and rel.parts[0] == "submission":
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
    """Package only files frozen in the current Git commit."""
    result = subprocess.run(
        [
            "git",
            "-C",
            str(ROOT),
            "ls-files",
            "-z",
            "--cached",
        ],
        check=False,
        capture_output=True,
        text=True,
        timeout=30,
    )
    if result.returncode != 0:
        raise RuntimeError("release packaging requires a readable Git worktree")
    return [ROOT / item for item in result.stdout.split("\0") if item]


def _worktree_status() -> list[str]:
    result = subprocess.run(
        [
            "git",
            "-C",
            str(ROOT),
            "status",
            "--porcelain=v1",
            "--untracked-files=all",
        ],
        check=False,
        capture_output=True,
        text=True,
        timeout=30,
    )
    if result.returncode != 0:
        raise RuntimeError("release packaging requires a readable Git worktree")
    return [line for line in result.stdout.splitlines() if line.strip()]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _git_value(*args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(ROOT), *args],
        check=False,
        capture_output=True,
        text=True,
        timeout=30,
    )
    value = result.stdout.strip()
    if result.returncode != 0 or not value:
        raise RuntimeError("release packaging requires a readable Git revision")
    return value


def _release_manifest(
    archive_format: str,
    files: list[Path],
    *,
    worktree_clean: bool,
) -> bytes:
    records = [
        {
            "path": path.relative_to(ROOT).as_posix(),
            "sha256": sha256(path),
            "size_bytes": path.stat().st_size,
        }
        for path in sorted(files, key=lambda item: item.relative_to(ROOT).as_posix())
    ]
    included_paths = {record["path"] for record in records}
    web_entrypoint = "apps/web/src/main.tsx"
    web_lockfile = "apps/web/package-lock.json"
    manifest = {
        "schema_version": "1.0",
        "project": "wifi-spatial-council",
        "version": VERSION,
        "archive_format": archive_format,
        "source": {
            "git_commit": _git_value("rev-parse", "HEAD"),
            "git_tree": _git_value("rev-parse", "HEAD^{tree}"),
            "worktree_clean": worktree_clean,
            "tracked_files_only": True,
        },
        "web_source": {
            "entrypoint": web_entrypoint,
            "lockfile": web_lockfile,
            "included": {
                "entrypoint": web_entrypoint in included_paths,
                "lockfile": web_lockfile in included_paths,
            },
        },
        "packaging_policy": {
            "untracked_files_included": False,
            "local_env_files_excluded": True,
            "raw_and_derived_capture_directories_excluded": True,
            "generated_artifacts_excluded": True,
            "private_submission_workbook_excluded": True,
        },
        "reproducibility": {
            "member_order": "path_ascending",
            "normalized_timestamp": "1980-01-01T00:00:00Z",
            "normalized_file_mode": "0644",
            "manifest_self_hash_excluded": True,
        },
        "files": records,
    }
    return (
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")


def _archive_name(archive_format: str) -> str:
    suffix = "zip" if archive_format == "zip" else "tar.gz"
    return f"wifi-spatial-council-{VERSION}.{suffix}"


def _archive_members(
    archive_format: str,
    files: list[Path],
    *,
    worktree_clean: bool,
) -> list[tuple[Path, bytes]]:
    members = [
        (ARCHIVE_ROOT / path.relative_to(ROOT), path.read_bytes())
        for path in files
    ]
    members.append(
        (
            ARCHIVE_ROOT / RELEASE_MANIFEST_NAME,
            _release_manifest(
                archive_format,
                files,
                worktree_clean=worktree_clean,
            ),
        )
    )
    return sorted(members, key=lambda item: item[0].as_posix())


def _local_path_leak_findings(
    members: list[tuple[Path, bytes]],
) -> list[str]:
    findings: set[str] = set()
    for member_path, content in members:
        member_name = member_path.as_posix()
        if any(marker in content for marker in ABSOLUTE_HOME_MARKERS):
            findings.add(f"{member_name}: absolute-home-path")
        for match in SERIAL_DEVICE_PATTERN.finditer(content):
            token = match.group(1).decode("ascii")
            if GENERIC_SERIAL_TOKEN.fullmatch(token):
                continue
            findings.add(f"{member_name}: concrete-serial-device")
    return sorted(findings)


def _assert_no_local_path_leaks(members: list[tuple[Path, bytes]]) -> None:
    findings = _local_path_leak_findings(members)
    if findings:
        raise RuntimeError(
            "release archive contains machine-specific local paths; "
            "only member names and finding classes are shown:\n"
            + "\n".join(findings)
        )


def _write_archive(
    archive: Path,
    archive_format: str,
    files: list[Path],
    *,
    worktree_clean: bool,
) -> None:
    files = [path for path in files if path.is_file() and _include(path)]
    members = _archive_members(
        archive_format,
        files,
        worktree_clean=worktree_clean,
    )
    _assert_no_local_path_leaks(members)
    if archive_format == "zip":
        with zipfile.ZipFile(
            archive,
            "w",
            compression=zipfile.ZIP_DEFLATED,
            compresslevel=9,
        ) as output:
            for arcname, content in members:
                info = zipfile.ZipInfo(arcname.as_posix(), date_time=ZIP_TIMESTAMP)
                info.compress_type = zipfile.ZIP_DEFLATED
                info.create_system = 3
                info.external_attr = (0o100644 & 0xFFFF) << 16
                output.writestr(info, content, compresslevel=9)
        return

    with archive.open("wb") as raw_output, gzip.GzipFile(
        filename="",
        mode="wb",
        fileobj=raw_output,
        compresslevel=9,
        mtime=0,
    ) as compressed_output, tarfile.open(
        fileobj=compressed_output,
        mode="w",
    ) as output:
        for arcname, content in members:
            info = tarfile.TarInfo(arcname.as_posix())
            info.size = len(content)
            info.mode = 0o644
            info.mtime = 0
            info.uid = 0
            info.gid = 0
            info.uname = ""
            info.gname = ""
            output.addfile(info, io.BytesIO(content))


def _extract_archive(archive: Path, archive_format: str, destination: Path) -> None:
    if archive_format == "zip":
        with zipfile.ZipFile(archive, "r") as source:
            source.extractall(destination)
        return
    with tarfile.open(archive, "r:gz") as source:
        source.extractall(destination)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", default="artifacts/release", type=Path)
    parser.add_argument(
        "--format",
        choices=("zip", "tar.gz"),
        default="zip",
        help="archive format; competition submissions should use zip (default)",
    )
    parser.add_argument(
        "--allow-dirty",
        action="store_true",
        help="development-only escape hatch; final competition ZIPs must remain clean",
    )
    args = parser.parse_args(argv)
    dirty = _worktree_status()
    if dirty and not args.allow_dirty:
        preview = "\n".join(dirty[:10])
        raise RuntimeError(
            "refusing to package a dirty worktree; commit the exact submission "
            f"candidate first. Current changes:\n{preview}"
        )
    out = args.output
    out.mkdir(parents=True, exist_ok=True)
    archive_name = _archive_name(args.format)
    archive = out / archive_name
    files = [
        path
        for path in sorted(_candidate_files())
        if path.is_file() and _include(path)
    ]
    _write_archive(
        archive,
        args.format,
        files,
        worktree_clean=not dirty,
    )

    checksum_path = out / f"{archive_name}.sha256"
    checksum_path.write_text(f"{sha256(archive)}  {archive_name}\n", encoding="utf-8")

    # Smoke: extract to a temp dir, verify checksum + structure + compile core.
    with tempfile.TemporaryDirectory() as tmp:
        extracted = Path(tmp) / "wifi-spatial-council"
        _extract_archive(archive, args.format, Path(tmp))
        rehash = sha256(archive)
        expected = checksum_path.read_text(encoding="utf-8").split()[0]
        assert rehash == expected, "archive checksum mismatch after write"
        missing = [
            name
            for name in REQUIRED_RELEASE_PATHS
            if not (extracted / name).is_file()
        ]
        assert not missing, f"archive missing: {missing}"
        manifest = json.loads(
            (extracted / RELEASE_MANIFEST_NAME).read_text(encoding="utf-8")
        )
        assert manifest["source"]["worktree_clean"] == (not dirty)
        assert manifest["source"]["git_commit"] == _git_value("rev-parse", "HEAD")
        for record in manifest["files"]:
            packaged_file = extracted / record["path"]
            assert packaged_file.stat().st_size == record["size_bytes"]
            assert sha256(packaged_file) == record["sha256"]
        extracted_members = [
            (ARCHIVE_ROOT / path.relative_to(extracted), path.read_bytes())
            for path in extracted.rglob("*")
            if path.is_file()
        ]
        _assert_no_local_path_leaks(extracted_members)
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
