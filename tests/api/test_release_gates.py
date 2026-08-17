"""Release evidence must fail closed when required metrics are absent."""

from __future__ import annotations

import json
import zipfile
from pathlib import Path

import pytest
from scripts.package_release import (
    RELEASE_MANIFEST_NAME,
    REQUIRED_RELEASE_PATHS,
    ROOT,
    _archive_name,
    _assert_no_local_path_leaks,
    _candidate_files,
    _extract_archive,
    _include,
    _local_path_leak_findings,
    _worktree_status,
    _write_archive,
    sha256,
)
from scripts.verify_release import soak_gate_status


def _soak(**overrides: object) -> dict[str, object]:
    report: dict[str, object] = {
        "duration_s": 3600.0,
        "crashes": 0,
        "queue_bounded": True,
        "rss_growth_under_10pct": True,
        "latency_p95_under_300ms": True,
    }
    report.update(overrides)
    return report


def test_soak_gate_requires_full_duration_and_all_metrics() -> None:
    assert soak_gate_status(None) == "not_run"
    assert soak_gate_status(_soak(duration_s=3599.9)) == "not_run"
    assert soak_gate_status(_soak()) == "passed"


def test_soak_gate_fails_invalid_memory_or_latency_evidence() -> None:
    assert soak_gate_status(_soak(rss_growth_under_10pct=False)) == "failed"
    assert soak_gate_status(_soak(latency_p95_under_300ms=False)) == "failed"
    assert soak_gate_status(_soak(latency_p95_under_300ms=None)) == "failed"


def test_release_archive_excludes_sensitive_raw_captures() -> None:
    assert not _include(ROOT / "data" / "raw" / "live-session" / "raw.csi.zst")
    assert _include(ROOT / "data" / "fixtures" / "demo_2min" / "raw.csi.zst")


def test_release_archive_excludes_local_env_but_keeps_example() -> None:
    assert not _include(ROOT / ".env")
    assert not _include(ROOT / ".env.production.local")
    assert _include(ROOT / ".env.example")


def test_release_archive_excludes_private_submission_workbook() -> None:
    assert not _include(ROOT / "submission" / "README.md")
    assert not _include(ROOT / "submission" / "captain-contact.txt")


def test_release_smoke_requires_competition_delivery_entrypoints() -> None:
    required = set(REQUIRED_RELEASE_PATHS)
    assert {
        "Dockerfile",
        "render.yaml",
        "SUBMISSION_README.md",
        "services/api/wifi_api/agent_routes.py",
        "services/api/wifi_api/mcp_server.py",
        "services/api/wifi_api/real_provider.py",
        "services/council/wifi_council/continuity.py",
        "services/council/wifi_council/deepseek.py",
        "scripts/mcp_smoke.py",
        "scripts/verify_openai_full_council.py",
    } <= required


def test_release_writer_cannot_include_private_submission_files(
    tmp_path: Path,
) -> None:
    archive = tmp_path / "submission-exclusion.zip"
    _write_archive(
        archive,
        "zip",
        [ROOT / "README.md", ROOT / "submission" / "README.md"],
        worktree_clean=False,
    )

    with zipfile.ZipFile(archive) as packaged:
        members = packaged.namelist()
    assert "wifi-spatial-council/README.md" in members
    assert not any(name.startswith("wifi-spatial-council/submission/") for name in members)


def test_release_path_scan_rejects_machine_paths_but_allows_placeholders() -> None:
    home_marker = b"/" + b"Users/owner/project"
    linux_home_marker = b"/" + b"home/owner/project"
    serial_prefix = b"/dev/" + b"cu."
    assert _local_path_leak_findings([(Path("a.txt"), home_marker)])
    assert _local_path_leak_findings([(Path("b.txt"), linux_home_marker)])
    assert _local_path_leak_findings(
        [(Path("c.txt"), serial_prefix + b"usbmodem101")]
    )
    assert not _local_path_leak_findings(
        [
            (
                Path("placeholders.txt"),
                b" ".join(
                    (
                        serial_prefix + b"X",
                        serial_prefix + b"usbmodemXXXX",
                        serial_prefix + b"usbmodemRXA",
                        serial_prefix + b"usbmodemYYYY",
                    )
                ),
            )
        ]
    )


def test_release_writer_fails_closed_on_machine_specific_content(
) -> None:
    with pytest.raises(RuntimeError, match="machine-specific local paths"):
        _assert_no_local_path_leaks(
            [
                (
                    Path("leaked.txt"),
                    b"workspace=" + b"/" + b"Users/owner/project",
                )
            ]
        )


def test_actual_release_candidates_have_no_machine_path_leaks() -> None:
    files = [
        path
        for path in _candidate_files()
        if path.is_file() and _include(path)
    ]
    members = [(path.relative_to(ROOT), path.read_bytes()) for path in files]
    assert _local_path_leak_findings(members) == []


def test_release_zip_is_the_default_competition_archive_shape(tmp_path: Path) -> None:
    archive = tmp_path / _archive_name("zip")
    _write_archive(
        archive,
        "zip",
        [ROOT / "README.md"],
        worktree_clean=False,
    )

    _extract_archive(archive, "zip", tmp_path / "extracted")

    extracted = tmp_path / "extracted" / "wifi-spatial-council" / "README.md"
    assert archive.name == "wifi-spatial-council-0.1.0.zip"
    assert extracted.read_bytes() == (ROOT / "README.md").read_bytes()


def test_release_zip_is_reproducible_and_has_auditable_manifest(
    tmp_path: Path,
) -> None:
    files = [
        ROOT / "README.md",
        ROOT / "apps" / "web" / "src" / "main.tsx",
        ROOT / "apps" / "web" / "package-lock.json",
    ]
    first = tmp_path / "first.zip"
    second = tmp_path / "second.zip"
    _write_archive(first, "zip", files, worktree_clean=True)
    _write_archive(second, "zip", list(reversed(files)), worktree_clean=True)

    assert first.read_bytes() == second.read_bytes()

    extracted_root = tmp_path / "manifest-extracted"
    _extract_archive(first, "zip", extracted_root)
    manifest = json.loads(
        (
            extracted_root
            / "wifi-spatial-council"
            / RELEASE_MANIFEST_NAME
        ).read_text(encoding="utf-8")
    )
    records = {record["path"]: record for record in manifest["files"]}
    assert manifest["version"] == "0.1.0"
    assert len(manifest["source"]["git_commit"]) == 40
    assert len(manifest["source"]["git_tree"]) == 40
    assert manifest["source"]["worktree_clean"] is True
    assert manifest["source"]["tracked_files_only"] is True
    assert manifest["web_source"]["included"] == {
        "entrypoint": True,
        "lockfile": True,
    }
    assert manifest["packaging_policy"]["untracked_files_included"] is False
    assert (
        manifest["packaging_policy"]["private_submission_workbook_excluded"] is True
    )
    assert records["README.md"]["sha256"] == sha256(ROOT / "README.md")
    assert RELEASE_MANIFEST_NAME not in records


def test_release_status_probe_reports_a_list_without_secrets() -> None:
    status = _worktree_status()
    assert isinstance(status, list)
    assert all("OPENAI_API_KEY=" not in line for line in status)
