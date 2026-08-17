"""CLI smoke: verify, inspect, replay, record."""

from __future__ import annotations

import json
from pathlib import Path

from wifi_collector.cli import main

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = ROOT / "data" / "fixtures" / "walk_through"


def test_cli_verify_fixture(capsys) -> None:
    assert main(["verify", str(FIXTURE)]) == 0
    assert "OK" in capsys.readouterr().out


def test_cli_inspect_fixture(capsys) -> None:
    assert main(["inspect", str(FIXTURE)]) == 0
    out = capsys.readouterr().out
    assert "session-fixture-walk-through" in out
    assert "/Users" not in out


def test_cli_replay_fixture(capsys) -> None:
    assert main(["replay", str(FIXTURE), "--no-pacing", "--count", "50"]) == 0
    out = capsys.readouterr().out
    assert "replayed 50 frames" in out


def test_cli_record_mock(tmp_path: Path) -> None:
    bundle = tmp_path / "raw"
    code = main(
        [
            "record",
            "--source",
            "mock",
            "--scenario",
            "idle",
            "--session-id",
            "sess-cli",
            "--out",
            str(bundle),
            "--duration",
            "0.2",
        ]
    )
    assert code == 0
    manifest = json.loads(
        (bundle / "sess-cli" / "manifest.json").read_text(encoding="utf-8")
    )
    assert manifest["status"] == "complete"
    assert manifest["source_mode"] == "mock"
