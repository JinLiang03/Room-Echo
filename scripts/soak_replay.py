#!/usr/bin/env python3
"""Replay soak: repeated demo_2min sessions for DURATION with bounded memory."""

from __future__ import annotations

import argparse
import asyncio
import gc
import json
import resource
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

from wifi_api.stream import BUFFER_LIMIT, StreamHub, StreamSession


def parse_duration(value: str) -> float:
    value = value.strip().lower()
    if value.endswith("m"):
        return float(value[:-1]) * 60
    if value.endswith("s"):
        return float(value[:-1])
    if value.endswith("h"):
        return float(value[:-1]) * 3600
    return float(value)


def max_rss_bytes() -> int:
    value = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    # macOS reports bytes; Linux reports KiB.
    return value if sys.platform == "darwin" else value * 1024


async def _run_one(session_id: int, hub: StreamHub) -> dict:
    session = StreamSession(
        bundle_root=Path("data/fixtures/demo_2min"),
        paced=False,
        demo_scenario=True,
    )
    hub.attach_session(session)
    session.start()
    while not session.status()["finished"] and not session.status()["error"]:
        await asyncio.sleep(0.05)
    return {
        "iteration": session_id,
        "events": hub._sequence,
        "queue_depth": len(hub._buffer),
        "windows": session.status()["windows"],
        "seals": session.status()["evidence_seals"],
        "error": session.status()["error"],
        "metrics": session.metrics(),
    }


async def _soak(duration_s: float, report_path: Path) -> dict:
    # Prime one complete session before the memory baseline so import caches,
    # model construction, and the first allocator high-water do not masquerade
    # as a long-run leak.
    warmup_hub = StreamHub()
    warmup = await _run_one(0, warmup_hub)
    gc.collect()

    started = time.monotonic()
    started_at = datetime.now(UTC).isoformat()
    start_rss = max_rss_bytes()
    iterations: list[dict] = []
    crashes = 0
    max_queue = 0
    total_events = 0
    iteration = 0
    latency_p95_values: list[float] = []

    while time.monotonic() - started < duration_s:
        iteration += 1
        hub = StreamHub()
        try:
            result = await _run_one(iteration, hub)
        except Exception as exc:  # soak must surface crashes
            crashes += 1
            iterations.append({"iteration": iteration, "crash": str(exc)[:300]})
            continue
        if result["error"]:
            crashes += 1
        iterations.append(result)
        max_queue = max(max_queue, result["queue_depth"])
        total_events += result["events"]
        latency = result.get("metrics", {}).get("window_latency_ms", {}).get("p95_ms")
        if isinstance(latency, int | float):
            latency_p95_values.append(float(latency))
        if iteration % 5 == 0:
            report = {
                "running": True,
                "iteration": iteration,
                "elapsed_s": round(time.monotonic() - started, 1),
                "max_queue": max_queue,
                "crashes": crashes,
            }
            report_path.write_text(
                json.dumps(report, indent=2) + "\n",
                encoding="utf-8",
            )
        await asyncio.sleep(0.05)

    elapsed_s = time.monotonic() - started
    end_rss = max_rss_bytes()
    rss_growth_pct = (
        (end_rss - start_rss) / max(start_rss, 1) * 100
    )
    latency_p95_max_ms = max(latency_p95_values) if latency_p95_values else None
    latency_p95_under_300ms = (
        latency_p95_max_ms is not None and latency_p95_max_ms < 300.0
    )
    return {
        "schema_version": "soak-replay.v1",
        "duration_s": round(elapsed_s, 1),
        "iterations": iteration,
        "crashes": crashes,
        "max_queue_depth": max_queue,
        "queue_limit": BUFFER_LIMIT,
        "queue_bounded": max_queue <= BUFFER_LIMIT,
        "total_events": total_events,
        "rss_start_bytes": start_rss,
        "rss_end_bytes": end_rss,
        "rss_growth_pct": round(rss_growth_pct, 3),
        "rss_growth_under_10pct": rss_growth_pct < 10.0,
        "latency_p95_max_ms": (
            round(latency_p95_max_ms, 3)
            if latency_p95_max_ms is not None
            else None
        ),
        "latency_p95_under_300ms": latency_p95_under_300ms,
        "warmup": {
            "windows": warmup.get("windows"),
            "error": warmup.get("error"),
        },
        "started_at": started_at,
        "finished_at": datetime.now(UTC).isoformat(),
        "iterations_sample": iterations[-20:],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--duration",
        default="60m",
        help="soak duration, e.g. 5m / 300s / 1h (default 60m)",
    )
    parser.add_argument(
        "--output",
        default="artifacts/web/soak_replay.json",
        type=Path,
    )
    args = parser.parse_args(argv)
    duration_s = parse_duration(args.duration)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    report = asyncio.run(_soak(duration_s, args.output))
    args.output.write_text(
        json.dumps(report, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(report, indent=2))
    if (
        report["crashes"] > 0
        or not report["queue_bounded"]
        or not report["rss_growth_under_10pct"]
        or not report["latency_p95_under_300ms"]
    ):
        print(
            "SOAK FAILED: requires zero crashes, bounded queue, RSS growth <10%, "
            "and window latency p95 <300 ms"
        )
        return 1
    print(f"SOAK OK: {report['iterations']} iterations, "
          f"max queue {report['max_queue_depth']}, "
          f"RSS growth {report['rss_growth_pct']:.2f}%, "
          f"latency p95 max {report['latency_p95_max_ms']:.2f} ms")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
