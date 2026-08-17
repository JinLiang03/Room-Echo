"""Collector CLI: ports, record, verify, replay, inspect."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path
from typing import cast

from .base import FrameSource
from .mock_source import SCENARIOS, MockFrameSource
from .replay_bundle import BundleVerifier
from .replay_source import ReplayFrameSource
from .serial_live import SerialLiveFrameSource


def _list_ports(_args: argparse.Namespace) -> int:
    try:
        import serial.tools.list_ports
    except ImportError:
        print("pyserial not installed; cannot list ports", file=sys.stderr)
        return 1
    ports = list(serial.tools.list_ports.comports())
    if not ports:
        print("no serial ports found")
        return 0
    for port in ports:
        print(f"{port.device}\t{port.description}")
    return 0


async def _record(args: argparse.Namespace) -> int:
    source: FrameSource
    if args.source == "mock":
        source = MockFrameSource(
            scenario=args.scenario,
            seed=args.seed,
            duration_s=args.duration,
            session_id=args.session_id,
            real_time=True,
        )
    elif args.source == "serial":
        source = SerialLiveFrameSource(
            session_id=args.session_id,
            rx_a_port=args.rx_a,
            rx_b_port=args.rx_b,
            baud=args.baud,
        )
    else:
        raise SystemExit(f"unknown source: {args.source}")

    from .recorder import RecordSession

    session = RecordSession(
        source=source,
        session_id=args.session_id,
        raw_root=Path(args.out),
    )
    try:
        path = await session.run(duration_s=args.duration if args.duration else None)
    finally:
        await source.close()
    print(f"recorded bundle: {path}")
    return 0


def _verify(args: argparse.Namespace) -> int:
    result = BundleVerifier(
        Path(args.replay),
        max_raw_bytes=args.max_raw_bytes,
    ).verify()
    if result.ok:
        print(
            f"OK {args.replay} "
            f"(raw {result.raw_bytes} bytes, "
            f"status={result.manifest.status if result.manifest else '?'})"
        )
        return 0
    for error in result.errors:
        print(f"FAIL: {error}", file=sys.stderr)
    return 1


async def _replay(args: argparse.Namespace) -> int:
    source = ReplayFrameSource(
        Path(args.replay),
        rate=args.rate,
        recompute=args.recompute,
        real_time=not args.no_pacing,
        max_raw_bytes=args.max_raw_bytes,
    )
    manifest = await source.open()
    count = 0
    first_seq: int | None = None
    last_seq: int | None = None
    links: set[str] = set()
    try:
        async for frame in source.frames():
            count += 1
            links.add(frame.link_id)
            if first_seq is None:
                first_seq = frame.seq
            last_seq = frame.seq
            if args.count is not None and count >= args.count:
                break
    finally:
        await source.close()
    health = await source.health()
    print(
        f"replayed {count} frames from {args.replay} "
        f"(links={sorted(links)}, first_seq={first_seq}, last_seq={last_seq}, "
        f"session={manifest.session_id}, status={health.status})"
    )
    return 0


def _inspect(args: argparse.Namespace) -> int:
    manifest_path = Path(args.replay) / "manifest.json"
    if not manifest_path.is_file():
        print(f"no manifest at {manifest_path}", file=sys.stderr)
        return 1
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    for key in (
        "recording_id",
        "session_id",
        "created_at",
        "source_mode",
        "firmware_version",
        "collector_version",
        "topology_hash",
        "channel",
        "bandwidth_mhz",
        "files",
        "ground_truth_present",
        "status",
    ):
        print(f"{key}: {manifest.get(key)}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="wsc-collector")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("ports", help="list serial ports")

    record = sub.add_parser("record", help="record a session into a raw bundle")
    record.add_argument("--source", choices=("mock", "serial"), default="mock")
    record.add_argument("--session-id", default="session-record")
    record.add_argument("--out", default="data/raw")
    record.add_argument("--scenario", choices=sorted(SCENARIOS), default="walk_through")
    record.add_argument("--seed", type=int, default=0xC5F15EED)
    record.add_argument("--duration", type=float, default=None)
    record.add_argument("--rx-a", default="")
    record.add_argument("--rx-b", default="")
    record.add_argument("--baud", type=int, default=921600)
    record.set_defaults(func=_record)

    verify = sub.add_parser("verify", help="verify a replay bundle")
    verify.add_argument("replay", type=Path)
    verify.add_argument("--max-raw-bytes", type=int, default=512 * 1024 * 1024)
    verify.set_defaults(func=_verify)

    replay = sub.add_parser("replay", help="replay a verified bundle")
    replay.add_argument("replay", type=Path)
    replay.add_argument("--rate", type=float, default=1.0)
    replay.add_argument("--count", type=int, default=None)
    replay.add_argument("--recompute", action="store_true")
    replay.add_argument("--no-pacing", action="store_true")
    replay.add_argument("--max-raw-bytes", type=int, default=512 * 1024 * 1024)
    replay.set_defaults(func=_replay)

    inspect = sub.add_parser("inspect", help="print bundle manifest fields")
    inspect.add_argument("replay", type=Path)
    inspect.set_defaults(func=_inspect)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    func = getattr(args, "func", None)
    if func is None:
        parser.print_help()
        return 2
    if asyncio.iscoroutinefunction(func):
        return cast(int, asyncio.run(func(args)))
    return cast(int, func(args))


if __name__ == "__main__":
    sys.exit(main())
