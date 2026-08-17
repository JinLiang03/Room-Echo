from pathlib import Path

from scripts.release_audit import _partition_copyleft_flags, _scan_secrets


def test_standalone_esptool_is_reviewed_without_hiding_runtime_copyleft() -> None:
    runtime, tooling = _partition_copyleft_flags(
        [
            {"name": "esptool", "license": "GPLv2+"},
            {"name": "runtime-gpl", "license": "GNU GPL v3"},
            {"name": "permissive", "license": "MIT"},
        ]
    )

    assert [row["name"] for row in runtime] == ["runtime-gpl"]
    assert [row["name"] for row in tooling] == ["esptool"]
    assert tooling[0]["scope"] == "standalone-development-tool"


def test_secret_scan_covers_packaged_fixture_metadata_but_skips_local_raw(
    tmp_path: Path,
) -> None:
    fixture = tmp_path / "data" / "fixtures" / "manifest.json"
    fixture.parent.mkdir(parents=True)
    fixture.write_text(
        '{"token": "' + "s" + 'k-abcdefghijklmnopqrstuvwxyz123456"}\n'
    )
    raw = tmp_path / "data" / "raw" / "local" / "manifest.json"
    raw.parent.mkdir(parents=True)
    raw.write_text(
        '{"token": "' + "s" + 'k-rawcaptureabcdefghijklmnopqrstuvwxyz"}\n'
    )

    findings = _scan_secrets(tmp_path)

    assert [finding["file"] for finding in findings] == [
        "data/fixtures/manifest.json"
    ]
