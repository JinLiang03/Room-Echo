#!/usr/bin/env python3
"""Release verification: run non-hardware gates and write release_report.json."""

from __future__ import annotations

import argparse
import json
import subprocess
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
REPLAY_REQUIRED_GATES = {
    "python-lint",
    "python-types",
    "contracts",
    "python-tests",
    "web-lint",
    "web-typecheck",
    "web-tests",
    "web-build",
    "multimodal-perf-smoke",
    "web-e2e",
    "e2e-replay",
    "fault-injection",
    "soak-replay-60m",
}


def soak_gate_status(soak: dict[str, Any] | None) -> str:
    """Return an honest status for the complete 60-minute Replay soak gate."""
    if not soak or float(soak.get("duration_s", 0)) < 3600:
        return "not_run"
    passed = (
        soak.get("crashes") == 0
        and soak.get("queue_bounded") is True
        and soak.get("rss_growth_under_10pct") is True
        and soak.get("latency_p95_under_300ms") is True
    )
    return "passed" if passed else "failed"


def _run(command: list[str], cwd: Path = ROOT, timeout_s: int = 1200) -> tuple[bool, str]:
    try:
        result = subprocess.run(
            command,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=timeout_s,
        )
        ok = result.returncode == 0
        tail = (result.stdout or result.stderr).strip().splitlines()[-8:]
        return ok, "\n".join(tail)
    except subprocess.TimeoutExpired:
        return False, f"timed out after {timeout_s}s"
    except FileNotFoundError as exc:
        return False, f"command not found: {exc}"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", default="replay", choices=["replay", "mock", "live"])
    parser.add_argument("--output", default="artifacts/release_report.json", type=Path)
    parser.add_argument("--skip-web-e2e", action="store_true")
    args = parser.parse_args(argv)

    gates: list[dict] = []

    def gate(name: str, command: list[str], cwd: Path = ROOT, timeout_s: int = 1200) -> None:
        print(f"running gate: {name}")
        started = time.monotonic()
        ok, tail = _run(command, cwd=cwd, timeout_s=timeout_s)
        gates.append(
            {
                "name": name,
                "status": "passed" if ok else "failed",
                "command": " ".join(command),
                "version": _version(command[0]),
                "elapsed_s": round(time.monotonic() - started, 1),
                "detail": tail,
                "artifact": None,
            }
        )
        if not ok:
            print(f"  FAILED:\n{tail}")

    gate("python-lint", ["uv", "run", "python", "-m", "ruff", "check", "."])
    gate("python-types", ["uv", "run", "python", "-m", "mypy", "services", "packages"])
    gate(
        "contracts",
        ["make", "verify-contracts"],
        timeout_s=300,
    )
    gate(
        "python-tests",
        ["uv", "run", "python", "-m", "pytest", "-m", "not hardware", "-q"],
        timeout_s=3600,
    )
    gate(
        "web-lint",
        ["npm", "--prefix", "apps/web", "run", "lint"],
        timeout_s=300,
    )
    gate(
        "web-typecheck",
        ["npm", "--prefix", "apps/web", "run", "typecheck"],
        timeout_s=300,
    )
    gate(
        "web-tests",
        ["npm", "--prefix", "apps/web", "run", "test"],
        timeout_s=600,
    )
    gate(
        "web-build",
        ["npm", "--prefix", "apps/web", "run", "build"],
        timeout_s=600,
    )
    gate(
        "multimodal-perf-smoke",
        ["make", "multimodal-perf-smoke"],
        timeout_s=300,
    )
    if not args.skip_web_e2e:
        gate(
            "web-e2e",
            ["npm", "--prefix", "apps/web", "run", "test:e2e"],
            timeout_s=1200,
        )
        gate(
            "e2e-replay",
            ["make", "e2e-replay"],
            timeout_s=1800,
        )
    else:
        for name, command in (
            ("web-e2e", "npm --prefix apps/web run test:e2e"),
            ("e2e-replay", "make e2e-replay"),
        ):
            gates.append(
                {
                    "name": name,
                    "status": "not_run",
                    "command": command,
                    "version": None,
                    "elapsed_s": None,
                    "detail": "explicitly skipped; cannot qualify a release candidate",
                    "artifact": None,
                }
            )
    gate("fault-injection", ["make", "fault-injection"], timeout_s=900)

    soak_path = ROOT / "artifacts" / "web" / "soak_replay.json"
    soak: dict[str, Any] | None = None
    if soak_path.is_file():
        soak = json.loads(soak_path.read_text(encoding="utf-8"))
    gates.append(
        {
            "name": "soak-replay-60m",
            "status": soak_gate_status(soak),
            "command": "make soak-replay DURATION=60m",
            "version": None,
            "elapsed_s": soak.get("duration_s") if soak else None,
            "detail": (
                f"iterations={soak.get('iterations')} max_queue={soak.get('max_queue_depth')} "
                f"rss_growth_pct={soak.get('rss_growth_pct')} "
                f"latency_p95_max_ms={soak.get('latency_p95_max_ms')}"
                if soak
                else "run `make soak-replay DURATION=60m` to produce evidence"
            ),
            "artifact": str(soak_path.relative_to(ROOT)) if soak else None,
        }
    )

    inventory_path = ROOT / "hardware" / "hardware_inventory.json"
    inventory: dict | None = None
    if inventory_path.is_file():
        inventory = json.loads(inventory_path.read_text(encoding="utf-8"))
    gates.append(
        {
            "name": "hardware-prerequisite-inventory",
            "status": (
                "passed"
                if inventory and inventory.get("status") == "ready"
                else "blocked_by_hardware"
            ),
            "command": "uv run python scripts/hardware_validate.py inventory",
            "version": None,
            "elapsed_s": None,
            "detail": (
                "; ".join(inventory.get("problems", []))
                if inventory
                else "inventory report missing"
            ),
            "artifact": (
                str(inventory_path.relative_to(ROOT)) if inventory else None
            ),
        }
    )

    live_status = (
        "not_run"
        if args.mode != "live"
        else "blocked_by_hardware"
    )
    gates.append(
        {
            "name": "live-30min-stability",
            "status": live_status,
            "command": "make live RX_PORTS=...",
            "version": None,
            "elapsed_s": None,
            "detail": (
                "requires physical ESP32 boards, antennas, and explicit serial ports; "
                "not validated in this environment"
                if live_status == "blocked_by_hardware"
                else "no hardware evidence"
            ),
            "artifact": None,
        }
    )
    gates.append(
        {
            "name": "same-room-heldout-signal-metrics",
            "status": "blocked_by_hardware",
            "command": "phase 11 calibration",
            "version": None,
            "elapsed_s": None,
            "detail": "requires physical room calibration; not run",
            "artifact": None,
        }
    )

    passed = sum(1 for gate_ in gates if gate_["status"] == "passed")
    failed = sum(1 for gate_ in gates if gate_["status"] == "failed")
    replay_candidate = all(
        gate_["status"] == "passed"
        for gate_ in gates
        if gate_["name"] in REPLAY_REQUIRED_GATES
    ) and REPLAY_REQUIRED_GATES.issubset({gate_["name"] for gate_ in gates})
    final_demo_ready = replay_candidate and all(
        gate_["status"] == "passed"
        for gate_ in gates
        if gate_["name"] in {
            "hardware-prerequisite-inventory",
            "live-30min-stability",
            "same-room-heldout-signal-metrics",
        }
    )
    report = {
        "schema_version": "release-report.v1",
        "mode": args.mode,
        "generated_at": datetime.now(UTC).isoformat(),
        "summary": {
            "passed": passed,
            "failed": failed,
            "not_run": sum(1 for g in gates if g["status"] == "not_run"),
            "blocked_by_hardware": sum(
                1 for g in gates if g["status"] == "blocked_by_hardware"
            ),
        },
        "release_candidate": replay_candidate,
        "final_demo_ready": final_demo_ready,
        "gates": gates,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(report["summary"], indent=2))
    print(f"report: {args.output}")
    return 0 if replay_candidate else 1


def _version(command: str) -> str | None:
    try:
        result = subprocess.run(
            [command, "--version"],
            capture_output=True,
            text=True,
            timeout=15,
        )
        if result.returncode == 0:
            return (result.stdout or result.stderr).strip().splitlines()[0][:120]
    except Exception:
        pass
    return None


if __name__ == "__main__":
    raise SystemExit(main())
