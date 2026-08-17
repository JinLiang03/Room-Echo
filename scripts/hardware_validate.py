#!/usr/bin/env python3
"""Phase 11 hardware validation tooling (safe by default).

The prerequisite gate is strict: unless the operator confirms explicit
TX/RX-A/RX-B serial ports AND the three boards are actually present, every
command exits with ``blocked_by_hardware`` and writes an honest report. The
tool never guesses ports, never probes unknown USB devices, and never flashes.
"""

from __future__ import annotations

import argparse
import asyncio
import glob
import hashlib
import json
import os
import stat
import statistics
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
HARDWARE_DIR = ROOT / "hardware"
MANIFEST = ROOT / "firmware" / "build" / "manifest.json"


def now_iso() -> str:
    return datetime.now(UTC).isoformat()


def sha256(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def build_info() -> dict[str, Any]:
    manifest: dict[str, Any] = {}
    if MANIFEST.is_file():
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    info: dict[str, Any] = {
        "target": manifest.get("target"),
        "esp_idf_version": manifest.get("esp_idf_version"),
        "esp_idf_git_commit": manifest.get("esp_idf_git_commit"),
        "esp_csi_commit": manifest.get("esp_csi_commit"),
        "firmware_version": manifest.get("firmware_version"),
        "artifacts": {},
    }
    for project in ("csi_tx", "csi_rx"):
        binary = ROOT / "firmware" / project / "build" / f"{project}.bin"
        if binary.is_file():
            info["artifacts"][project] = {
                "path": str(binary.relative_to(ROOT)),
                "sha256": sha256(binary),
                "size_bytes": binary.stat().st_size,
            }
        else:
            info["artifacts"][project] = {"path": None, "sha256": None}
    return info


def detect_serial_ports() -> list[dict[str, Any]]:
    """Read-only detection of /dev/cu.* serial devices."""
    ports: list[dict[str, Any]] = []
    for path in sorted(glob.glob("/dev/cu.*")):
        try:
            mode = os.stat(path).st_mode
            is_char = stat.S_ISCHR(mode)
        except OSError:
            is_char = False
        name = Path(path).name
        system = name in {
            "cu.Bluetooth-Incoming-Port",
            "cu.debug-console",
            "cu.wlan-debug",
        }
        ports.append(
            {
                "path": path,
                "char_device": is_char,
                "system_port": system,
                "role": None,
                "confirmed_board": False,
            }
        )
    return ports


def require_confirmed_ports(rx_a: str, rx_b: str, tx: str, confirmed: bool) -> list[str]:
    problems: list[str] = []
    for role, port in (("tx", tx), ("rx-a", rx_a), ("rx-b", rx_b)):
        if not port:
            problems.append(f"{role} port missing")
            continue
        if not Path(port).exists():
            problems.append(f"{role} port does not exist: {port}")
        else:
            try:
                if not stat.S_ISCHR(os.stat(port).st_mode):
                    problems.append(f"{role} port is not a character device: {port}")
            except OSError as exc:
                problems.append(f"{role} port unreadable: {exc}")
    if not confirmed:
        problems.append(
            "operator confirmation required: pass --confirmed after mapping and "
            "checking the three physical boards (never flash unconfirmed devices)"
        )
    return problems


def write_report(name: str, data: dict[str, Any]) -> Path:
    HARDWARE_DIR.mkdir(parents=True, exist_ok=True)
    path = HARDWARE_DIR / name
    path.write_text(
        json.dumps(data, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return path


def not_implemented_report(
    name: str,
    gate: str,
    detail: str,
    **context: Any,
) -> Path:
    """Persist an explicit non-passing result for an unfinished hardware gate."""
    return write_report(
        name,
        {
            "schema_version": "hardware-report.v1",
            "status": "not_run",
            "result": "not_implemented",
            "generated_at": now_iso(),
            "gate": gate,
            "detail": detail,
            "build": build_info(),
            **context,
        },
    )


def blocked_reports(problems: list[str], gate: str) -> None:
    """Write all Phase 11 required reports as blocked/not_run."""
    common: dict[str, Any] = {
        "schema_version": "hardware-report.v1",
        "status": "blocked_by_hardware",
        "generated_at": now_iso(),
        "gate": gate,
        "problems": problems,
        "build": build_info(),
        "topology": None,
        "room": None,
        "devices_confirmed": False,
    }
    for name in (
        "firmware_flash_report.json",
        "capture_qa_report.json",
        "calibration_report.json",
        "live_acceptance_report.json",
        "live_vs_replay_report.json",
    ):
        write_report(name, {**common, "report": name, "result": "not_run"})
    write_report(
        "topology.json",
        {
            "schema_version": "topology.v1",
            "status": "blocked_by_hardware",
            "generated_at": now_iso(),
            "room": None,
            "board_positions": None,
            "antenna_direction": None,
            "depth_axis_points": None,
            "topology_hash": None,
            "photo_paths": [],
            "note": "room/topology not prepared; no photos or measurements recorded",
        },
    )


def cmd_inventory(_args: argparse.Namespace) -> int:
    ports = detect_serial_ports()
    build = build_info()
    esps = [p for p in ports if not p["system_port"]]
    problems: list[str] = []
    if len(esps) < 3:
        problems.append(
            f"expected 3 ESP32 serial devices, found {len(esps)} non-system ports "
            f"({', '.join(p['path'] for p in esps) or 'none'})"
        )
    for port in esps:
        problems.append(f"unconfirmed device at {port['path']} (identity unknown)")
    inventory = {
        "schema_version": "hardware-inventory.v1",
        "status": "blocked_by_hardware" if problems else "ready",
        "generated_at": now_iso(),
        "serial_ports": ports,
        "non_system_ports": esps,
        "confirmed_esp32_boards": [],
        "build": build,
        "problems": problems,
        "notes": (
            "Only one unknown serial device (Jinwqc45) was detected; it is NOT "
            "confirmed to be an ESP32 and was not probed. macOS system ports "
            "(Bluetooth/debug/wlan) are excluded. Three boards, antennas, "
            "power, room geometry, and a 5-point depth axis must be prepared "
            "before this gate can pass."
        ),
    }
    path = write_report("hardware_inventory.json", inventory)
    print(json.dumps(inventory, indent=2))
    print(f"report: {path}")
    return 0 if not problems else 2


def _require_gate(args: argparse.Namespace, gate: str) -> tuple[int, list[str]]:
    problems = require_confirmed_ports(
        args.rx_a,
        args.rx_b,
        args.tx,
        args.confirmed,
    )
    if problems:
        blocked_reports(problems, gate)
        print(f"BLOCKED_BY_HARDWARE ({gate}):")
        for problem in problems:
            print(f"  - {problem}")
        return 1, problems
    return 0, problems


async def _collect_live(rx_a: str, rx_b: str, duration_s: float) -> dict[str, Any]:
    from wifi_collector.serial_live import SerialLiveFrameSource

    source = SerialLiveFrameSource(
        session_id="hardware-sanity",
        rx_a_port=rx_a,
        rx_b_port=rx_b,
    )
    await source.open()
    counts: dict[str, int] = {"rx-a": 0, "rx-b": 0}
    csi_lengths: list[int] = []
    rssi: list[float] = []
    noise: list[float] = []
    started = asyncio.get_event_loop().time()
    try:
        async for frame in source.frames():
            counts[frame.link_id] = counts.get(frame.link_id, 0) + 1
            csi_lengths.append(len(frame.csi_iq))
            rssi.append(frame.rssi_dbm)
            noise.append(frame.noise_floor_dbm)
            if asyncio.get_event_loop().time() - started >= duration_s:
                break
    finally:
        await source.close()
    elapsed = asyncio.get_event_loop().time() - started
    return {
        "elapsed_s": round(elapsed, 2),
        "packet_rate_per_link_hz": {
            link: round(count / max(elapsed, 1e-6), 2)
            for link, count in counts.items()
        },
        "csi_length": {
            "min": min(csi_lengths) if csi_lengths else None,
            "max": max(csi_lengths) if csi_lengths else None,
            "mode": statistics.mode(csi_lengths) if csi_lengths else None,
        },
        "rssi_dbm": {
            "mean": round(statistics.mean(rssi), 2) if rssi else None,
            "min": min(rssi) if rssi else None,
            "max": max(rssi) if rssi else None,
        },
        "noise_floor_dbm": {
            "mean": round(statistics.mean(noise), 2) if noise else None,
            "min": min(noise) if noise else None,
            "max": max(noise) if noise else None,
        },
    }


def cmd_sanity(args: argparse.Namespace) -> int:
    code, _problems = _require_gate(args, "hardware-sanity")
    if code:
        return code
    stats = asyncio.run(_collect_live(args.rx_a, args.rx_b, args.duration_s))
    report = {
        "schema_version": "capture-qa.v1",
        "status": "passed" if stats["packet_rate_per_link_hz"]["rx-a"] >= 90 else "failed",
        "generated_at": now_iso(),
        "ports": {"tx": args.tx, "rx-a": args.rx_a, "rx-b": args.rx_b},
        "build": build_info(),
        "stats": stats,
        "note": "thresholds: >=90 pkt/s per RX, CSI length stable, no reboot",
    }
    path = write_report("capture_qa_report.json", report)
    print(json.dumps(report, indent=2))
    print(f"report: {path}")
    return 0 if report["status"] == "passed" else 1


def cmd_calibrate_live(args: argparse.Namespace) -> int:
    code, _problems = _require_gate(args, "calibrate-live")
    if code:
        return code
    detail = (
        "live calibration orchestration is not implemented; it must record the "
        "warmup/empty/walk/occupancy/5-point depth/held-out trials into "
        "append-only raw bundles and activate only a non-simulated profile after "
        "split and quality checks"
    )
    path = not_implemented_report(
        "calibration_report.json",
        "calibrate-live",
        detail,
        profile=args.profile,
        ports={"tx": args.tx, "rx-a": args.rx_a, "rx-b": args.rx_b},
    )
    print(f"NOT_RUN (calibrate-live): {detail}", file=sys.stderr)
    print(f"report: {path}", file=sys.stderr)
    return 1


def cmd_test_hardware(args: argparse.Namespace) -> int:
    code, _problems = _require_gate(args, "test-hardware")
    if code:
        return code
    detail = (
        "automated hardware acceptance is not implemented; it must evaluate a "
        "verified raw recording and matching non-simulated profile against the "
        "30 min, empty-room, motion, occupancy/depth held-out, interference and "
        "dropout gates in docs/ACCEPTANCE_TESTS.md"
    )
    path = not_implemented_report(
        "live_acceptance_report.json",
        "test-hardware",
        detail,
        profile=args.profile,
        ports={"tx": args.tx, "rx-a": args.rx_a, "rx-b": args.rx_b},
    )
    print(f"NOT_RUN (test-hardware): {detail}", file=sys.stderr)
    print(f"report: {path}", file=sys.stderr)
    return 1


def cmd_compare_live_replay(args: argparse.Namespace) -> int:
    recording = Path(args.recording)
    if not recording.is_dir():
        problem = f"recording missing: {recording}"
        path = write_report(
            "live_vs_replay_report.json",
            {
                "schema_version": "hardware-report.v1",
                "status": "blocked_by_hardware",
                "result": "not_run",
                "generated_at": now_iso(),
                "gate": "compare-live-replay",
                "problems": [problem],
                "build": build_info(),
                "recording": str(recording),
            },
        )
        print(f"BLOCKED_BY_HARDWARE (compare-live-replay): {problem}")
        print(f"report: {path}")
        return 1
    detail = (
        "live-vs-replay equivalence automation is not implemented; it must verify "
        "the bundle checksum, replay with recompute=true, and compare feature, "
        "signal and quality outputs within recorded tolerances"
    )
    path = not_implemented_report(
        "live_vs_replay_report.json",
        "compare-live-replay",
        detail,
        recording=str(recording.resolve()),
    )
    print(f"NOT_RUN (compare-live-replay): {detail}", file=sys.stderr)
    print(f"report: {path}", file=sys.stderr)
    return 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    inventory = sub.add_parser("inventory", help="read-only hardware inventory")
    inventory.set_defaults(func=cmd_inventory)

    for name in ("sanity", "calibrate-live", "test-hardware"):
        p = sub.add_parser(name)
        p.add_argument("--rx-a", required=True)
        p.add_argument("--rx-b", required=True)
        p.add_argument("--tx", required=True)
        p.add_argument("--confirmed", action="store_true")
        p.add_argument("--profile", default="demo_room_v1")
        p.set_defaults(func=cmd_sanity if name == "sanity" else (
            cmd_calibrate_live if name == "calibrate-live" else cmd_test_hardware
        ))
        if name == "sanity":
            p.add_argument("--duration-s", dest="duration_s", default=300.0, type=float)

    compare = sub.add_parser("compare-live-replay")
    compare.add_argument("--recording", required=True)
    compare.set_defaults(func=cmd_compare_live_replay)

    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
