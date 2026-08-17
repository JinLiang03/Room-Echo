#!/usr/bin/env python3
"""Generate a fail-closed, secret-minimised demo version manifest.

The output always evaluates two independent gates:

* ``replay_candidate`` accepts a verified mock/replay bundle and may use an
  explicitly labelled simulated calibration profile.
* ``final_demo_ready`` requires a live raw bundle, a recorded non-simulated
  profile, a ready topology, matching firmware, and all Phase 11 reports.

Only allow-listed metadata and content hashes are copied into the output.
Raw CSI, topology geometry, serial ports, report prose, environment values,
and Git dirty-file names are deliberately excluded.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError
from wifi_collector.replay_bundle import (
    CHECKSUMS_FILE,
    MANIFEST_FILE,
    BundleVerifier,
    ReplayManifest,
)
from wifi_contracts import CONTRACTS_VERSION, HASH_PATTERN
from wifi_sensing.calibration import CalibrationProfile

ROOT = Path(__file__).resolve().parents[1]
ZERO_HASH = "sha256:" + "0" * 64
HASH_RE = re.compile(HASH_PATTERN)
EXPECTED_HARDWARE_REPORTS = (
    "firmware_flash_report.json",
    "capture_qa_report.json",
    "calibration_report.json",
    "live_acceptance_report.json",
    "live_vs_replay_report.json",
)
REPLAY_TOPOLOGY_STATUSES = {
    "complete",
    "fixture",
    "passed",
    "ready",
    "simulated",
    "validated",
}
FINAL_TOPOLOGY_STATUSES = {"complete", "passed", "ready", "validated"}
PASS_STATUSES = {"complete", "ok", "passed", "ready", "validated"}


class FileEvidence(BaseModel):
    """Safe file evidence: no absolute path and no file contents."""

    path: str
    present: bool
    sha256: str | None = None
    size_bytes: int | None = None


class GitEvidence(BaseModel):
    available: bool
    commit: str | None = None
    branch: str | None = None
    detached: bool = False
    dirty: bool | None = None


class FirmwareEvidence(BaseModel):
    manifest_file: FileEvidence
    valid: bool
    schema_version: str | None = None
    generated_at: str | None = None
    target: str | None = None
    firmware_version: str | None = None
    esp_idf_version: str | None = None
    esp_idf_git_commit: str | None = None
    esp_csi_commit: str | None = None
    projects: list[str] = Field(default_factory=list)
    tx_binary: FileEvidence
    rx_binary: FileEvidence


class ReplayManifestSummary(BaseModel):
    schema_version: str
    recording_id: str
    session_id: str
    created_at: str
    source_mode: str
    firmware_version: str
    collector_version: str
    contracts_version: str
    features_version: str | None
    estimator_version: str | None
    board_hashes: dict[str, str]
    topology_hash: str
    calibration_profile_id: str | None
    channel: int
    bandwidth_mhz: int
    ground_truth_present: bool
    status: str


class ReplayBundleEvidence(BaseModel):
    path: str
    present: bool
    verified: bool
    verification_errors: list[str] = Field(default_factory=list)
    raw_bytes: int
    manifest_file: FileEvidence
    checksums_file: FileEvidence
    manifest: ReplayManifestSummary | None = None


class CalibrationEvidence(BaseModel):
    file: FileEvidence
    valid: bool
    schema_version: str | None = None
    profile_id: str | None = None
    topology_hash: str | None = None
    feature_version: str | None = None
    firmware_version: str | None = None
    channel: int | None = None
    bandwidth_mhz: int | None = None
    checksum: str | None = None
    computed_checksum: str | None = None
    integrity: bool = False
    source: str | None = None
    simulated: bool | None = None
    metrics_simulated: bool | None = None
    state: str | None = None
    fitted_at: str | None = None
    max_age_days: int | None = None
    board_hashes: dict[str, str] = Field(default_factory=dict)
    has_fit_parameters: bool = False
    has_metrics: bool = False


class TopologyInput(BaseModel):
    model_config = ConfigDict(extra="ignore")

    schema_version: Literal["topology.v1"]
    status: str = Field(min_length=1)
    topology_hash: str | None = Field(default=None, pattern=HASH_PATTERN)


class TopologyEvidence(BaseModel):
    file: FileEvidence
    valid: bool
    schema_version: str | None = None
    status: str | None = None
    topology_hash: str | None = None


class HardwareReportEvidence(BaseModel):
    file: FileEvidence
    valid: bool
    schema_version: str | None = None
    status: str | None = None
    result: str | None = None
    passed: bool = False
    topology_hash: str | None = None
    firmware_hashes: dict[str, str] = Field(default_factory=dict)


class GateIssue(BaseModel):
    code: str
    detail: str


class GateEvidence(BaseModel):
    status: Literal["ready", "blocked"]
    blockers: list[GateIssue] = Field(default_factory=list)
    warnings: list[GateIssue] = Field(default_factory=list)

    @property
    def ready(self) -> bool:
        return self.status == "ready"


class DemoVersionManifest(BaseModel):
    schema_version: Literal["demo-version-manifest.v1"] = "demo-version-manifest.v1"
    generated_at: datetime
    contracts_version: str
    git: GitEvidence
    firmware: FirmwareEvidence
    replay_bundle: ReplayBundleEvidence
    calibration_profile: CalibrationEvidence
    topology: TopologyEvidence
    hardware_reports: dict[str, HardwareReportEvidence]
    replay_candidate: GateEvidence
    final_demo_ready: GateEvidence


@dataclass(frozen=True)
class ManifestInputs:
    repo_root: Path
    bundle: Path
    profile: Path
    topology: Path
    firmware_manifest: Path
    tx_binary: Path
    rx_binary: Path
    hardware_reports: dict[str, Path]
    max_raw_bytes: int = 512 * 1024 * 1024


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return "sha256:" + digest.hexdigest()


def _display_path(path: Path, repo_root: Path) -> str:
    """Return a repository-relative path, or only a basename for external data."""
    try:
        return path.resolve().relative_to(repo_root.resolve()).as_posix()
    except ValueError:
        return path.name


def _file_evidence(path: Path, repo_root: Path) -> FileEvidence:
    if not path.is_file():
        return FileEvidence(path=_display_path(path, repo_root), present=False)
    return FileEvidence(
        path=_display_path(path, repo_root),
        present=True,
        sha256=_sha256(path),
        size_bytes=path.stat().st_size,
    )


def _git_command(repo_root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(repo_root), *args],
        check=False,
        capture_output=True,
        text=True,
        timeout=5,
    )


def inspect_git(repo_root: Path) -> GitEvidence:
    """Read Git identity without recording dirty filenames."""
    try:
        inside = _git_command(repo_root, "rev-parse", "--is-inside-work-tree")
    except (OSError, subprocess.SubprocessError):
        return GitEvidence(available=False)
    if inside.returncode != 0 or inside.stdout.strip() != "true":
        return GitEvidence(available=False)

    try:
        commit_result = _git_command(repo_root, "rev-parse", "HEAD")
        branch_result = _git_command(repo_root, "symbolic-ref", "--short", "-q", "HEAD")
        dirty_result = _git_command(
            repo_root,
            "status",
            "--porcelain",
            "--untracked-files=all",
        )
    except (OSError, subprocess.SubprocessError):
        return GitEvidence(available=False)
    commit = commit_result.stdout.strip() if commit_result.returncode == 0 else None
    branch = branch_result.stdout.strip() if branch_result.returncode == 0 else None
    dirty = None if dirty_result.returncode != 0 else bool(dirty_result.stdout.strip())
    return GitEvidence(
        available=commit is not None and dirty is not None,
        commit=commit,
        branch=branch,
        detached=branch is None and commit is not None,
        dirty=dirty,
    )


def _safe_bundle_errors(
    errors: list[str],
    repo_root: Path,
    bundle_path: Path,
) -> list[str]:
    replacements = sorted(
        (
            (str(repo_root.resolve()), "."),
            (str(bundle_path.resolve()), _display_path(bundle_path, repo_root)),
        ),
        key=lambda item: len(item[0]),
        reverse=True,
    )
    safe: list[str] = []
    for error in errors:
        cleaned = error
        for source, replacement in replacements:
            cleaned = cleaned.replace(source, replacement)
        safe.append(cleaned[:500])
    return safe


def _manifest_summary(manifest: ReplayManifest) -> ReplayManifestSummary:
    return ReplayManifestSummary(
        schema_version=manifest.schema_version,
        recording_id=manifest.recording_id,
        session_id=manifest.session_id,
        created_at=manifest.created_at.isoformat(),
        source_mode=manifest.source_mode,
        firmware_version=manifest.firmware_version,
        collector_version=manifest.collector_version,
        contracts_version=manifest.contracts_version,
        features_version=manifest.features_version,
        estimator_version=manifest.estimator_version,
        board_hashes=manifest.board_hashes,
        topology_hash=manifest.topology_hash,
        calibration_profile_id=manifest.calibration_profile_id,
        channel=manifest.channel,
        bandwidth_mhz=manifest.bandwidth_mhz,
        ground_truth_present=manifest.ground_truth_present,
        status=manifest.status,
    )


def inspect_bundle(inputs: ManifestInputs) -> ReplayBundleEvidence:
    path = inputs.bundle
    result = BundleVerifier(path, max_raw_bytes=inputs.max_raw_bytes).verify()
    return ReplayBundleEvidence(
        path=_display_path(path, inputs.repo_root),
        present=path.is_dir(),
        verified=result.ok,
        verification_errors=_safe_bundle_errors(
            result.errors,
            inputs.repo_root,
            path,
        ),
        raw_bytes=result.raw_bytes,
        manifest_file=_file_evidence(path / MANIFEST_FILE, inputs.repo_root),
        checksums_file=_file_evidence(path / CHECKSUMS_FILE, inputs.repo_root),
        manifest=_manifest_summary(result.manifest) if result.manifest else None,
    )


def _read_json_object(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return value if isinstance(value, dict) else None


def inspect_profile(path: Path, repo_root: Path) -> CalibrationEvidence:
    file = _file_evidence(path, repo_root)
    data = _read_json_object(path)
    if data is None:
        return CalibrationEvidence(file=file, valid=False)
    try:
        profile = CalibrationProfile.model_validate(data)
    except ValidationError:
        return CalibrationEvidence(file=file, valid=False)
    metrics_simulated = profile.metrics.simulated if profile.metrics else None
    return CalibrationEvidence(
        file=file,
        valid=True,
        schema_version=profile.schema_version,
        profile_id=profile.profile_id,
        topology_hash=profile.topology_hash,
        feature_version=profile.feature_version,
        firmware_version=profile.firmware_version,
        channel=profile.channel,
        bandwidth_mhz=profile.bandwidth_mhz,
        checksum=profile.checksum,
        computed_checksum=profile.compute_checksum(),
        integrity=profile.verify_integrity(),
        source=profile.source,
        simulated=profile.simulated,
        metrics_simulated=metrics_simulated,
        state=profile.state,
        fitted_at=profile.fitted_at.isoformat(),
        max_age_days=profile.expiry.max_age_days,
        board_hashes=profile.board_hashes,
        has_fit_parameters=profile.fit_parameters is not None,
        has_metrics=profile.metrics is not None,
    )


def inspect_topology(path: Path, repo_root: Path) -> TopologyEvidence:
    file = _file_evidence(path, repo_root)
    data = _read_json_object(path)
    if data is None:
        return TopologyEvidence(file=file, valid=False)
    try:
        topology = TopologyInput.model_validate(data)
    except ValidationError:
        return TopologyEvidence(file=file, valid=False)
    return TopologyEvidence(
        file=file,
        valid=True,
        schema_version=topology.schema_version,
        status=topology.status.lower(),
        topology_hash=topology.topology_hash,
    )


def _firmware_hash_from_container(data: dict[str, Any], project: str) -> str | None:
    for container_name in ("artifacts", "binaries"):
        container = data.get(container_name)
        if not isinstance(container, dict):
            continue
        entry = container.get(project)
        if isinstance(entry, dict) and isinstance(entry.get("sha256"), str):
            return str(entry["sha256"])
    return None


def inspect_firmware(inputs: ManifestInputs) -> FirmwareEvidence:
    manifest_file = _file_evidence(inputs.firmware_manifest, inputs.repo_root)
    tx_file = _file_evidence(inputs.tx_binary, inputs.repo_root)
    rx_file = _file_evidence(inputs.rx_binary, inputs.repo_root)
    data = _read_json_object(inputs.firmware_manifest)
    if data is None:
        return FirmwareEvidence(
            manifest_file=manifest_file,
            valid=False,
            tx_binary=tx_file,
            rx_binary=rx_file,
        )

    projects_value = data.get("projects")
    projects = (
        [str(item) for item in projects_value if isinstance(item, str)]
        if isinstance(projects_value, list)
        else []
    )
    required_strings = ("schema_version", "target", "firmware_version")
    valid = all(isinstance(data.get(key), str) and data[key] for key in required_strings)
    return FirmwareEvidence(
        manifest_file=manifest_file,
        valid=valid,
        schema_version=_short_string(data.get("schema_version")),
        generated_at=_short_string(data.get("generated_at")),
        target=_short_string(data.get("target")),
        firmware_version=_short_string(data.get("firmware_version")),
        esp_idf_version=_short_string(data.get("esp_idf_version")),
        esp_idf_git_commit=_short_string(data.get("esp_idf_git_commit")),
        esp_csi_commit=_short_string(data.get("esp_csi_commit")),
        projects=projects,
        tx_binary=tx_file,
        rx_binary=rx_file,
    )


def _short_string(value: object, *, limit: int = 200) -> str | None:
    if not isinstance(value, str) or not value:
        return None
    return value[:limit]


def _extract_topology_hash(data: dict[str, Any]) -> str | None:
    direct = data.get("topology_hash")
    if isinstance(direct, str) and HASH_RE.fullmatch(direct):
        return direct
    topology = data.get("topology")
    if isinstance(topology, dict):
        nested = topology.get("topology_hash")
        if isinstance(nested, str) and HASH_RE.fullmatch(nested):
            return nested
    return None


def _extract_report_firmware_hashes(data: dict[str, Any]) -> dict[str, str]:
    build = data.get("build")
    if not isinstance(build, dict):
        return {}
    hashes: dict[str, str] = {}
    for project in ("csi_tx", "csi_rx"):
        value = _firmware_hash_from_container(build, project)
        if value is not None and HASH_RE.fullmatch(value):
            hashes[project] = value
    return hashes


def inspect_hardware_report(path: Path, repo_root: Path) -> HardwareReportEvidence:
    file = _file_evidence(path, repo_root)
    data = _read_json_object(path)
    if data is None:
        return HardwareReportEvidence(file=file, valid=False)
    schema_version = _short_string(data.get("schema_version"), limit=80)
    status = _short_string(data.get("status"), limit=80)
    result = _short_string(data.get("result"), limit=80)
    normalized_status = status.lower() if status else None
    normalized_result = result.lower() if result else None
    passed = bool(
        schema_version
        and normalized_status in PASS_STATUSES
        and (normalized_result is None or normalized_result in PASS_STATUSES)
    )
    return HardwareReportEvidence(
        file=file,
        valid=schema_version is not None and status is not None,
        schema_version=schema_version,
        status=normalized_status,
        result=normalized_result,
        passed=passed,
        topology_hash=_extract_topology_hash(data),
        firmware_hashes=_extract_report_firmware_hashes(data),
    )


def _issue(issues: list[GateIssue], code: str, detail: str) -> None:
    if any(item.code == code for item in issues):
        return
    issues.append(GateIssue(code=code, detail=detail))


def _normalized_firmware_version(value: str | None) -> str | None:
    if value is None:
        return None
    prefix = "wifi-spatial-council-fw/"
    return value[len(prefix) :] if value.startswith(prefix) else value


def _shared_blockers(
    *,
    git: GitEvidence,
    firmware: FirmwareEvidence,
    bundle: ReplayBundleEvidence,
    profile: CalibrationEvidence,
    topology: TopologyEvidence,
    firmware_manifest_data: dict[str, Any] | None,
) -> list[GateIssue]:
    blockers: list[GateIssue] = []
    if not git.available or not git.commit:
        _issue(blockers, "git_unavailable", "Git commit provenance is unavailable")
    elif git.dirty is not False:
        _issue(blockers, "git_dirty", "the Git worktree has tracked or untracked changes")

    if not firmware.manifest_file.present:
        _issue(blockers, "firmware_manifest_missing", "firmware build manifest is missing")
    elif not firmware.valid:
        _issue(blockers, "firmware_manifest_invalid", "firmware build manifest is invalid")
    if not firmware.tx_binary.present:
        _issue(blockers, "firmware_tx_missing", "TX firmware binary is missing")
    if not firmware.rx_binary.present:
        _issue(blockers, "firmware_rx_missing", "RX firmware binary is missing")
    if firmware.valid and not {"csi_tx", "csi_rx"}.issubset(set(firmware.projects)):
        _issue(
            blockers,
            "firmware_projects_missing",
            "firmware manifest does not identify both csi_tx and csi_rx",
        )
    if firmware_manifest_data:
        for project, evidence in (
            ("csi_tx", firmware.tx_binary),
            ("csi_rx", firmware.rx_binary),
        ):
            expected = _firmware_hash_from_container(firmware_manifest_data, project)
            if expected is not None and expected != evidence.sha256:
                _issue(
                    blockers,
                    f"firmware_{project}_hash_mismatch",
                    f"{project} binary hash does not match the firmware manifest",
                )

    if not bundle.present:
        _issue(blockers, "bundle_missing", "replay bundle directory is missing")
    elif not bundle.verified:
        _issue(blockers, "bundle_verification_failed", "BundleVerifier rejected the bundle")
    manifest = bundle.manifest
    if manifest is None:
        _issue(blockers, "bundle_manifest_missing", "validated replay manifest is unavailable")
    elif manifest.contracts_version != CONTRACTS_VERSION:
        _issue(
            blockers,
            "contracts_version_mismatch",
            "bundle contracts version does not match the runtime contracts version",
        )

    if not profile.file.present:
        _issue(blockers, "profile_missing", "calibration profile is missing")
    elif not profile.valid:
        _issue(blockers, "profile_invalid", "calibration profile does not validate")
    else:
        if not profile.integrity:
            _issue(blockers, "profile_checksum_mismatch", "profile checksum integrity failed")
        if profile.state != "active":
            _issue(blockers, "profile_inactive", "calibration profile is not active")

    if not topology.file.present:
        _issue(blockers, "topology_missing", "topology record is missing")
    elif not topology.valid:
        _issue(blockers, "topology_invalid", "topology record does not validate")
    elif topology.topology_hash is None:
        _issue(blockers, "topology_hash_missing", "topology record has no topology hash")

    if manifest is not None and profile.valid:
        if manifest.topology_hash != profile.topology_hash:
            _issue(
                blockers,
                "bundle_profile_topology_mismatch",
                "bundle and calibration profile topology hashes differ",
            )
        if manifest.calibration_profile_id is None:
            _issue(
                blockers,
                "bundle_profile_id_missing",
                "bundle does not pin a calibration profile id",
            )
        elif manifest.calibration_profile_id != profile.profile_id:
            _issue(
                blockers,
                "bundle_profile_id_mismatch",
                "bundle and calibration profile ids differ",
            )
        if manifest.channel != profile.channel:
            _issue(blockers, "channel_mismatch", "bundle and profile channels differ")
        if manifest.bandwidth_mhz != profile.bandwidth_mhz:
            _issue(blockers, "bandwidth_mismatch", "bundle and profile bandwidths differ")
        if manifest.features_version and manifest.features_version != profile.feature_version:
            _issue(
                blockers,
                "feature_version_mismatch",
                "bundle and profile feature versions differ",
            )
    if (
        manifest is not None
        and topology.topology_hash is not None
        and manifest.topology_hash != topology.topology_hash
    ):
        _issue(
            blockers,
            "bundle_topology_mismatch",
            "bundle and topology record hashes differ",
        )
    if (
        profile.valid
        and topology.topology_hash is not None
        and profile.topology_hash != topology.topology_hash
    ):
        _issue(
            blockers,
            "profile_topology_mismatch",
            "profile and topology record hashes differ",
        )
    return blockers


def _gate(status_blockers: list[GateIssue], warnings: list[GateIssue]) -> GateEvidence:
    return GateEvidence(
        status="blocked" if status_blockers else "ready",
        blockers=status_blockers,
        warnings=warnings,
    )


def _replay_gate(
    shared: list[GateIssue],
    *,
    git: GitEvidence,
    bundle: ReplayBundleEvidence,
    profile: CalibrationEvidence,
    topology: TopologyEvidence,
    hardware_reports: dict[str, HardwareReportEvidence],
) -> GateEvidence:
    blockers = list(shared)
    warnings: list[GateIssue] = []
    manifest = bundle.manifest
    if manifest is not None and manifest.source_mode not in {"mock", "replay"}:
        _issue(
            blockers,
            "replay_source_mode_invalid",
            "replay candidate requires a verified mock or replay source bundle",
        )
    if topology.status not in REPLAY_TOPOLOGY_STATUSES:
        _issue(
            blockers,
            "topology_not_replay_ready",
            "topology status is not suitable for a replay candidate",
        )
    if profile.simulated:
        _issue(
            warnings,
            "simulated_profile",
            "profile is simulated and may only be presented as replay/mock evidence",
        )
    if profile.source == "demo":
        _issue(
            warnings,
            "demo_profile",
            "demo profile is not evidence of live hardware calibration",
        )
    if manifest is not None and manifest.source_mode == "mock":
        _issue(
            warnings,
            "mock_bundle",
            "bundle is deterministic mock data, not a live hardware recording",
        )
    if topology.status in {"fixture", "simulated"}:
        _issue(
            warnings,
            "simulated_topology",
            "topology is suitable only for replay/mock presentation",
        )
    if not all(report.passed for report in hardware_reports.values()):
        _issue(
            warnings,
            "hardware_gates_not_passed",
            "hardware gates are not required for replay, but final demo remains blocked",
        )
    if git.detached:
        _issue(warnings, "git_detached", "Git commit is pinned but HEAD is detached")
    return _gate(blockers, warnings)


def _final_gate(
    shared: list[GateIssue],
    *,
    bundle: ReplayBundleEvidence,
    profile: CalibrationEvidence,
    topology: TopologyEvidence,
    firmware: FirmwareEvidence,
    hardware_reports: dict[str, HardwareReportEvidence],
    generated_at: datetime,
) -> GateEvidence:
    blockers = list(shared)
    warnings: list[GateIssue] = []
    manifest = bundle.manifest
    if manifest is None or manifest.source_mode != "live":
        _issue(
            blockers,
            "live_bundle_required",
            "final demo requires a verified bundle recorded from source_mode=live",
        )

    if profile.source != "recorded":
        _issue(blockers, "recorded_profile_required", "final profile source must be recorded")
    if profile.simulated is not False:
        _issue(
            blockers,
            "non_simulated_profile_required",
            "final profile must explicitly carry simulated=false",
        )
    if not profile.has_fit_parameters:
        _issue(blockers, "fit_parameters_missing", "final profile has no fitted parameters")
    if not profile.has_metrics:
        _issue(blockers, "profile_metrics_missing", "final profile has no held-out metrics")
    elif profile.metrics_simulated is not False:
        _issue(
            blockers,
            "non_simulated_metrics_required",
            "final profile metrics must explicitly carry simulated=false",
        )
    if profile.fitted_at and profile.max_age_days is not None:
        try:
            fitted_at = datetime.fromisoformat(profile.fitted_at)
            if fitted_at.tzinfo is None:
                fitted_at = fitted_at.replace(tzinfo=UTC)
            age_days = (generated_at - fitted_at).total_seconds() / 86400
            if age_days > profile.max_age_days:
                _issue(blockers, "profile_expired", "calibration profile exceeds max_age_days")
        except ValueError:
            _issue(blockers, "profile_timestamp_invalid", "profile fitted_at is invalid")

    if topology.status not in FINAL_TOPOLOGY_STATUSES:
        _issue(
            blockers,
            "topology_not_final_ready",
            "final topology status must be ready, passed, validated, or complete",
        )

    firmware_version = _normalized_firmware_version(firmware.firmware_version)
    if manifest is not None and manifest.source_mode == "live":
        if _normalized_firmware_version(manifest.firmware_version) != firmware_version:
            _issue(
                blockers,
                "bundle_firmware_version_mismatch",
                "live bundle firmware version does not match the build manifest",
            )
        for link_id in ("rx-a", "rx-b"):
            board_hash = manifest.board_hashes.get(link_id)
            if board_hash in {None, ZERO_HASH} or not HASH_RE.fullmatch(board_hash or ""):
                _issue(
                    blockers,
                    f"bundle_{link_id}_board_hash_missing",
                    f"live bundle does not pin a non-placeholder {link_id} board hash",
                )
            elif profile.board_hashes.get(link_id) != board_hash:
                _issue(
                    blockers,
                    f"profile_{link_id}_board_hash_mismatch",
                    f"profile and live bundle {link_id} board hashes differ",
                )
    if _normalized_firmware_version(profile.firmware_version) != firmware_version:
        _issue(
            blockers,
            "profile_firmware_version_mismatch",
            "profile firmware version does not match the build manifest",
        )

    expected_hashes = {
        "csi_tx": firmware.tx_binary.sha256,
        "csi_rx": firmware.rx_binary.sha256,
    }
    for name in EXPECTED_HARDWARE_REPORTS:
        report = hardware_reports[name]
        if not report.file.present:
            _issue(
                blockers,
                f"hardware_report_missing:{name}",
                f"required hardware report is missing: {name}",
            )
            continue
        if not report.valid:
            _issue(
                blockers,
                f"hardware_report_invalid:{name}",
                f"required hardware report is invalid: {name}",
            )
            continue
        if not report.passed:
            _issue(
                blockers,
                f"hardware_report_not_passed:{name}",
                f"required hardware report did not pass: {name}",
            )
            # One honest not-passed blocker is sufficient. Pin validation is
            # meaningful only for a report that claims to have passed; avoid
            # flooding operators with derivative missing/mismatch messages
            # from deliberately fail-closed placeholder reports.
            continue
        if report.topology_hash is None:
            _issue(
                blockers,
                f"hardware_report_topology_hash_missing:{name}",
                f"hardware report does not pin the topology hash: {name}",
            )
        elif report.topology_hash != topology.topology_hash:
            _issue(
                blockers,
                f"hardware_report_topology_hash_mismatch:{name}",
                f"hardware report topology hash differs: {name}",
            )
        for project, expected_hash in expected_hashes.items():
            reported_hash = report.firmware_hashes.get(project)
            if reported_hash is None:
                _issue(
                    blockers,
                    f"hardware_report_{project}_hash_missing:{name}",
                    f"hardware report does not pin {project} firmware: {name}",
                )
            elif reported_hash != expected_hash:
                _issue(
                    blockers,
                    f"hardware_report_{project}_hash_mismatch:{name}",
                    f"hardware report {project} hash differs: {name}",
                )
    return _gate(blockers, warnings)


def generate_manifest(
    inputs: ManifestInputs,
    *,
    git_override: GitEvidence | None = None,
    generated_at: datetime | None = None,
) -> DemoVersionManifest:
    """Inspect all inputs and produce both independent readiness decisions."""
    instant = generated_at or datetime.now(UTC)
    if instant.tzinfo is None:
        instant = instant.replace(tzinfo=UTC)
    git = git_override or inspect_git(inputs.repo_root)
    firmware_manifest_data = _read_json_object(inputs.firmware_manifest)
    firmware = inspect_firmware(inputs)
    bundle = inspect_bundle(inputs)
    profile = inspect_profile(inputs.profile, inputs.repo_root)
    topology = inspect_topology(inputs.topology, inputs.repo_root)
    reports = {
        name: inspect_hardware_report(
            inputs.hardware_reports.get(
                name,
                inputs.repo_root / "hardware" / name,
            ),
            inputs.repo_root,
        )
        for name in EXPECTED_HARDWARE_REPORTS
    }
    shared = _shared_blockers(
        git=git,
        firmware=firmware,
        bundle=bundle,
        profile=profile,
        topology=topology,
        firmware_manifest_data=firmware_manifest_data,
    )
    return DemoVersionManifest(
        generated_at=instant,
        contracts_version=CONTRACTS_VERSION,
        git=git,
        firmware=firmware,
        replay_bundle=bundle,
        calibration_profile=profile,
        topology=topology,
        hardware_reports=reports,
        replay_candidate=_replay_gate(
            shared,
            git=git,
            bundle=bundle,
            profile=profile,
            topology=topology,
            hardware_reports=reports,
        ),
        final_demo_ready=_final_gate(
            shared,
            bundle=bundle,
            profile=profile,
            topology=topology,
            firmware=firmware,
            hardware_reports=reports,
            generated_at=instant,
        ),
    )


def _rooted(repo_root: Path, value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else repo_root / path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--repo-root", default=str(ROOT))
    parser.add_argument("--bundle", default="data/fixtures/demo_2min")
    parser.add_argument(
        "--profile",
        default="data/calibration/demo_room_v1/profile.json",
    )
    parser.add_argument(
        "--topology",
        default="data/calibration/demo_room_v1/topology.json",
        help=(
            "topology record matching the selected bundle/profile; pass "
            "hardware/topology.json explicitly for a live candidate"
        ),
    )
    parser.add_argument("--firmware-manifest", default="firmware/build/manifest.json")
    parser.add_argument("--tx-bin", default="firmware/csi_tx/build/csi_tx.bin")
    parser.add_argument("--rx-bin", default="firmware/csi_rx/build/csi_rx.bin")
    parser.add_argument("--hardware-dir", default="hardware")
    parser.add_argument(
        "--output",
        default="artifacts/handoff/demo-version-manifest.json",
    )
    parser.add_argument(
        "--gate",
        choices=("replay_candidate", "final_demo_ready"),
        default="replay_candidate",
        help="gate used for the process exit code; both gates are always emitted",
    )
    parser.add_argument("--max-raw-bytes", type=int, default=512 * 1024 * 1024)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    repo_root = Path(args.repo_root).resolve()
    hardware_dir = _rooted(repo_root, args.hardware_dir)
    inputs = ManifestInputs(
        repo_root=repo_root,
        bundle=_rooted(repo_root, args.bundle),
        profile=_rooted(repo_root, args.profile),
        topology=_rooted(repo_root, args.topology),
        firmware_manifest=_rooted(repo_root, args.firmware_manifest),
        tx_binary=_rooted(repo_root, args.tx_bin),
        rx_binary=_rooted(repo_root, args.rx_bin),
        hardware_reports={
            name: hardware_dir / name for name in EXPECTED_HARDWARE_REPORTS
        },
        max_raw_bytes=args.max_raw_bytes,
    )
    manifest = generate_manifest(inputs)
    output = _rooted(repo_root, args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(output.suffix + ".tmp")
    temporary.write_text(
        manifest.model_dump_json(indent=2) + "\n",
        encoding="utf-8",
    )
    temporary.replace(output)

    print(f"manifest: {_display_path(output, repo_root)}")
    print(f"replay_candidate: {manifest.replay_candidate.status}")
    print(f"final_demo_ready: {manifest.final_demo_ready.status}")
    selected: GateEvidence = getattr(manifest, args.gate)
    for blocker in selected.blockers:
        print(f"BLOCKER [{blocker.code}] {blocker.detail}")
    return 0 if selected.ready else 1


if __name__ == "__main__":
    raise SystemExit(main())
