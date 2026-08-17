"""Fail-closed demo version manifest tests."""

from __future__ import annotations

import hashlib
import json
import shutil
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path

import pytest
from scripts import generate_demo_manifest as demo_manifest
from wifi_sensing.calibration import CalibrationProfile

PROJECT_ROOT = Path(__file__).resolve().parents[2]
NOW = datetime(2026, 8, 7, 12, 0, tzinfo=UTC)
TOPOLOGY_HASH = "sha256:" + "3" * 64
RX_A_HASH = "sha256:" + "a" * 64
RX_B_HASH = "sha256:" + "b" * 64


def _sha256(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def _write_json(path: Path, data: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def _clean_git() -> demo_manifest.GitEvidence:
    return demo_manifest.GitEvidence(
        available=True,
        commit="1" * 40,
        branch="main",
        detached=False,
        dirty=False,
    )


def _codes(gate: demo_manifest.GateEvidence) -> set[str]:
    return {issue.code for issue in gate.blockers}


def _warning_codes(gate: demo_manifest.GateEvidence) -> set[str]:
    return {issue.code for issue in gate.warnings}


def _workspace(
    tmp_path: Path,
    *,
    live: bool = False,
    hardware_passed: bool = False,
) -> demo_manifest.ManifestInputs:
    root = tmp_path / "workspace"
    bundle = root / "recordings" / "demo"
    shutil.copytree(PROJECT_ROOT / "data" / "fixtures" / "demo_2min", bundle)

    manifest_path = bundle / "manifest.json"
    replay_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    replay_manifest.update(
        {
            "source_mode": "live" if live else "mock",
            "firmware_version": ("wifi-spatial-council-fw/0.1.0" if live else "0.0.0-mock"),
            "features_version": "features-v2",
            "topology_hash": TOPOLOGY_HASH,
            "calibration_profile_id": "demo_room_v1",
            "board_hashes": {"rx-a": RX_A_HASH, "rx-b": RX_B_HASH},
        }
    )
    _write_json(manifest_path, replay_manifest)

    profile_path = root / "calibration" / "profile.json"
    profile_data = json.loads(
        (PROJECT_ROOT / "tests" / "signals" / "fixtures" / "profile.json").read_text(
            encoding="utf-8"
        )
    )
    profile_data.update(
        {
            "topology_hash": TOPOLOGY_HASH,
            "firmware_version": "wifi-spatial-council-fw/0.1.0",
            "board_hashes": {"rx-a": RX_A_HASH, "rx-b": RX_B_HASH},
            "fitted_at": "2026-08-07T08:00:00Z",
            "source": "recorded",
            "simulated": not live,
            "state": "active",
        }
    )
    profile_data["metrics"]["simulated"] = not live
    profile_data["metrics"]["evaluated_at"] = "2026-08-07T09:00:00Z"
    profile = CalibrationProfile.model_validate(profile_data)
    profile.checksum = profile.compute_checksum()
    _write_json(profile_path, profile.model_dump(mode="json"))

    topology_path = root / "hardware" / "topology.json"
    _write_json(
        topology_path,
        {
            "schema_version": "topology.v1",
            "status": "ready" if live else "simulated",
            "topology_hash": TOPOLOGY_HASH,
            "board_positions": {"secret-geometry": "must-not-leak"},
            "photo_paths": ["/private/room.jpg"],
        },
    )

    tx_binary = root / "firmware" / "csi_tx.bin"
    rx_binary = root / "firmware" / "csi_rx.bin"
    tx_binary.parent.mkdir(parents=True)
    tx_binary.write_bytes(b"tx-firmware")
    rx_binary.write_bytes(b"rx-firmware")
    firmware_manifest = root / "firmware" / "manifest.json"
    _write_json(
        firmware_manifest,
        {
            "schema_version": "1.0.0",
            "generated_at": "2026-08-07T07:00:00Z",
            "target": "esp32s3",
            "firmware_version": "0.1.0",
            "esp_idf_version": "ESP-IDF v5.5.2",
            "esp_idf_git_commit": "2" * 40,
            "esp_csi_commit": "3" * 40,
            "projects": ["csi_tx", "csi_rx"],
            "artifacts": {
                "csi_tx": {"sha256": _sha256(tx_binary)},
                "csi_rx": {"sha256": _sha256(rx_binary)},
            },
        },
    )

    report_paths: dict[str, Path] = {}
    for name in demo_manifest.EXPECTED_HARDWARE_REPORTS:
        report_path = root / "hardware" / name
        report_paths[name] = report_path
        _write_json(
            report_path,
            {
                "schema_version": "hardware-report.v1",
                "status": "passed" if hardware_passed else "blocked_by_hardware",
                "result": "passed" if hardware_passed else "not_run",
                "topology_hash": TOPOLOGY_HASH if hardware_passed else None,
                "serial_ports": ["/dev/secret-device"],
                "operator_note": "must-not-leak",
                "build": {
                    "artifacts": {
                        "csi_tx": {"sha256": _sha256(tx_binary)},
                        "csi_rx": {"sha256": _sha256(rx_binary)},
                    }
                },
            },
        )

    return demo_manifest.ManifestInputs(
        repo_root=root,
        bundle=bundle,
        profile=profile_path,
        topology=topology_path,
        firmware_manifest=firmware_manifest,
        tx_binary=tx_binary,
        rx_binary=rx_binary,
        hardware_reports=report_paths,
    )


def test_replay_candidate_accepts_explicit_simulation_but_final_blocks(
    tmp_path: Path,
) -> None:
    inputs = _workspace(tmp_path)

    result = demo_manifest.generate_manifest(
        inputs,
        git_override=_clean_git(),
        generated_at=NOW,
    )

    assert result.replay_candidate.status == "ready"
    assert result.final_demo_ready.status == "blocked"
    assert {"simulated_profile", "mock_bundle", "simulated_topology"} <= (
        _warning_codes(result.replay_candidate)
    )
    assert {
        "live_bundle_required",
        "non_simulated_profile_required",
        "non_simulated_metrics_required",
        "topology_not_final_ready",
    } <= _codes(result.final_demo_ready)

    rendered = result.model_dump_json()
    assert str(tmp_path) not in rendered
    assert "secret-geometry" not in rendered
    assert "/dev/secret-device" not in rendered
    assert "must-not-leak" not in rendered


def test_final_demo_ready_requires_and_accepts_complete_live_evidence(
    tmp_path: Path,
) -> None:
    inputs = _workspace(tmp_path, live=True, hardware_passed=True)

    result = demo_manifest.generate_manifest(
        inputs,
        git_override=_clean_git(),
        generated_at=NOW,
    )

    assert result.final_demo_ready.status == "ready"
    assert result.final_demo_ready.blockers == []
    assert result.replay_candidate.status == "blocked"
    assert "replay_source_mode_invalid" in _codes(result.replay_candidate)
    assert result.firmware.tx_binary.sha256 == _sha256(inputs.tx_binary)
    assert result.firmware.rx_binary.sha256 == _sha256(inputs.rx_binary)
    assert result.calibration_profile.integrity is True
    assert all(report.passed for report in result.hardware_reports.values())


@pytest.mark.parametrize(
    ("mutation", "expected_code"),
    [
        ("dirty", "git_dirty"),
        ("bundle", "bundle_verification_failed"),
        ("profile", "profile_checksum_mismatch"),
        ("topology", "bundle_topology_mismatch"),
        ("firmware", "firmware_csi_tx_hash_mismatch"),
    ],
)
def test_integrity_failures_block_both_gates(
    tmp_path: Path,
    mutation: str,
    expected_code: str,
) -> None:
    inputs = _workspace(tmp_path)
    git = _clean_git()
    if mutation == "dirty":
        git = git.model_copy(update={"dirty": True})
    elif mutation == "bundle":
        with (inputs.bundle / "raw.csi.zst").open("ab") as handle:
            handle.write(b"tamper")
    elif mutation == "profile":
        profile = json.loads(inputs.profile.read_text(encoding="utf-8"))
        profile["room_id"] = "tampered-room"
        _write_json(inputs.profile, profile)
    elif mutation == "topology":
        topology = json.loads(inputs.topology.read_text(encoding="utf-8"))
        topology["topology_hash"] = "sha256:" + "9" * 64
        _write_json(inputs.topology, topology)
    elif mutation == "firmware":
        inputs.tx_binary.write_bytes(b"tampered-firmware")

    result = demo_manifest.generate_manifest(
        inputs,
        git_override=git,
        generated_at=NOW,
    )

    assert expected_code in _codes(result.replay_candidate)
    assert expected_code in _codes(result.final_demo_ready)


def test_final_fails_closed_for_missing_or_unpinned_hardware_reports(
    tmp_path: Path,
) -> None:
    inputs = _workspace(tmp_path, live=True, hardware_passed=True)
    missing_name = demo_manifest.EXPECTED_HARDWARE_REPORTS[0]
    inputs.hardware_reports[missing_name].unlink()
    unpinned_name = demo_manifest.EXPECTED_HARDWARE_REPORTS[1]
    report = json.loads(inputs.hardware_reports[unpinned_name].read_text(encoding="utf-8"))
    report["topology_hash"] = None
    report["build"] = {}
    _write_json(inputs.hardware_reports[unpinned_name], report)

    result = demo_manifest.generate_manifest(
        inputs,
        git_override=_clean_git(),
        generated_at=NOW,
    )

    codes = _codes(result.final_demo_ready)
    assert f"hardware_report_missing:{missing_name}" in codes
    assert f"hardware_report_topology_hash_missing:{unpinned_name}" in codes
    assert f"hardware_report_csi_tx_hash_missing:{unpinned_name}" in codes
    assert f"hardware_report_csi_rx_hash_missing:{unpinned_name}" in codes


def test_cli_writes_both_gates_and_uses_selected_gate_for_exit(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    inputs = _workspace(tmp_path)
    output = tmp_path / "manifest-output.json"
    monkeypatch.setattr(demo_manifest, "inspect_git", lambda _root: _clean_git())
    common = [
        "--repo-root",
        str(inputs.repo_root),
        "--bundle",
        str(inputs.bundle),
        "--profile",
        str(inputs.profile),
        "--topology",
        str(inputs.topology),
        "--firmware-manifest",
        str(inputs.firmware_manifest),
        "--tx-bin",
        str(inputs.tx_binary),
        "--rx-bin",
        str(inputs.rx_binary),
        "--hardware-dir",
        str(inputs.topology.parent),
        "--output",
        str(output),
    ]

    assert demo_manifest.main([*common, "--gate", "replay_candidate"]) == 0
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["replay_candidate"]["status"] == "ready"
    assert payload["final_demo_ready"]["status"] == "blocked"
    assert demo_manifest.main([*common, "--gate", "final_demo_ready"]) == 1


def test_missing_inputs_are_reported_in_manifest_instead_of_crashing(
    tmp_path: Path,
) -> None:
    inputs = _workspace(tmp_path)
    missing = tmp_path / "missing"
    inputs = replace(
        inputs,
        bundle=missing / "bundle",
        profile=missing / "profile.json",
        topology=missing / "topology.json",
        firmware_manifest=missing / "firmware.json",
        tx_binary=missing / "tx.bin",
        rx_binary=missing / "rx.bin",
        hardware_reports={name: missing / name for name in demo_manifest.EXPECTED_HARDWARE_REPORTS},
    )

    result = demo_manifest.generate_manifest(
        inputs,
        git_override=_clean_git(),
        generated_at=NOW,
    )

    codes = _codes(result.replay_candidate)
    assert {
        "bundle_missing",
        "profile_missing",
        "topology_missing",
        "firmware_manifest_missing",
        "firmware_tx_missing",
        "firmware_rx_missing",
    } <= codes


def test_bundle_errors_redact_external_absolute_path(tmp_path: Path) -> None:
    repo_root = tmp_path / "workspace"
    external_bundle = tmp_path / "private-captures" / "secret-recording"

    errors = demo_manifest._safe_bundle_errors(
        [f"verification failed at {external_bundle}/raw.csi.zst"],
        repo_root,
        external_bundle,
    )

    assert str(tmp_path) not in errors[0]
    assert "secret-recording/raw.csi.zst" in errors[0]
