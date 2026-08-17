"""End-to-end wizard (mock) and evaluate CLI."""

from __future__ import annotations

import json
from pathlib import Path

from scripts.calibration_wizard import main as wizard_main
from scripts.evaluate_calibration import main as evaluate_main


def test_wizard_mock_end_to_end(tmp_path: Path) -> None:
    out = tmp_path / "cal"
    code = wizard_main(
        [
            "--mode",
            "mock",
            "--scenario",
            "demo_room_v1",
            "--out",
            str(out),
            "--duration-s",
            "2.5",
            "--seed",
            "7",
        ]
    )
    assert code == 0
    profile_dir = out / "demo_room_v1"
    profile = json.loads((profile_dir / "profile.json").read_text(encoding="utf-8"))
    assert profile["simulated"] is True
    assert profile["state"] == "active"
    assert profile["checksum"].startswith("sha256:")
    assert (profile_dir / "calibration_report.json").is_file()
    assert (profile_dir / "calibration_report.html").is_file()
    report = json.loads(
        (profile_dir / "calibration_report.json").read_text(encoding="utf-8")
    )
    assert report["simulated"] is True
    assert any("not hardware" in item.lower() for item in report["limitations"])


def test_evaluate_cli_reports_simulated(tmp_path: Path, capsys) -> None:
    out = tmp_path / "cal"
    assert wizard_main(
        [
            "--mode",
            "mock",
            "--scenario",
            "demo_room_v1",
            "--out",
            str(out),
            "--duration-s",
            "2.5",
            "--seed",
            "9",
        ]
    ) == 0
    code = evaluate_main(["--profile", str(out / "demo_room_v1")])
    assert code == 0
    captured = capsys.readouterr().out
    assert "SIMULATED — NOT HARDWARE EVIDENCE" in captured
    assert (out / "demo_room_v1" / "evaluation_rerun.json").is_file()


def test_evaluate_rejects_tampered_profile(tmp_path: Path, capsys) -> None:
    out = tmp_path / "cal"
    assert wizard_main(
        [
            "--mode",
            "mock",
            "--scenario",
            "demo_room_v1",
            "--out",
            str(out),
            "--duration-s",
            "2.5",
            "--seed",
            "5",
        ]
    ) == 0
    profile_path = out / "demo_room_v1" / "profile.json"
    profile = json.loads(profile_path.read_text(encoding="utf-8"))
    profile["room_id"] = "different_room"
    profile_path.write_text(json.dumps(profile), encoding="utf-8")
    assert evaluate_main(["--profile", str(out / "demo_room_v1")]) == 1
    assert "checksum mismatch" in capsys.readouterr().err
