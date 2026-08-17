"""Truthfulness checks for the Phase 11/12 hardware handoff commands."""

from __future__ import annotations

import json
from pathlib import Path

from scripts import hardware_validate


def test_compare_missing_recording_writes_blocked_report(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setattr(hardware_validate, "HARDWARE_DIR", tmp_path / "reports")
    missing = tmp_path / "missing-bundle"

    code = hardware_validate.main(["compare-live-replay", "--recording", str(missing)])

    report = json.loads((tmp_path / "reports" / "live_vs_replay_report.json").read_text())
    assert code == 1
    assert report["status"] == "blocked_by_hardware"
    assert report["result"] == "not_run"
    assert report["recording"] == str(missing)


def test_compare_existing_recording_is_explicitly_not_implemented(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setattr(hardware_validate, "HARDWARE_DIR", tmp_path / "reports")
    recording = tmp_path / "raw-bundle"
    recording.mkdir()

    code = hardware_validate.main(["compare-live-replay", "--recording", str(recording)])

    report = json.loads((tmp_path / "reports" / "live_vs_replay_report.json").read_text())
    assert code == 1
    assert report["status"] == "not_run"
    assert report["result"] == "not_implemented"
    assert report["recording"] == str(recording.resolve())
