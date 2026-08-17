#!/usr/bin/env python3
"""One-command demo launcher: preflight, start API+Web, progress, stop."""

from __future__ import annotations

import argparse
import json
import os
import signal
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _http_json(url: str, timeout: float = 3.0):
    with urllib.request.urlopen(url, timeout=timeout) as response:
        return json.load(response)


def preflight(args: argparse.Namespace) -> list[str]:
    problems: list[str] = []
    if args.mode == "replay":
        bundle = ROOT / "data" / "fixtures" / args.scenario
        if not (bundle / "manifest.json").is_file():
            problems.append(
                f"replay bundle not found: {bundle} (run `uv run python scripts/generate_fixtures.py`)"
            )
    if args.mode not in ("replay", "mock"):
        problems.append(f"mode must be replay or mock, got {args.mode!r}")
    return problems


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", default="replay", choices=["replay", "mock"])
    parser.add_argument("--scenario", default="walk_through")
    parser.add_argument("--api-port", default=8000, type=int)
    parser.add_argument("--web-port", default=5173, type=int)
    parser.add_argument("--no-browser", action="store_true")
    parser.add_argument("--max-seconds", default=180, type=int)
    args = parser.parse_args(argv)

    problems = preflight(args)
    if problems:
        for problem in problems:
            print(f"PREFLIGHT FAIL: {problem}", file=sys.stderr)
        return 1
    print(f"PREFLIGHT OK: mode={args.mode} scenario={args.scenario}")

    env = os.environ.copy()
    env.update({
        "APP_MODE": args.mode,
        "SCENARIO": args.scenario,
        "DEMO_AUTOSTART": "1",
    })
    api = subprocess.Popen(
        [
            "uv", "run", "uvicorn", "wifi_api.app:app",
            "--host", "127.0.0.1", "--port", str(args.api_port),
        ],
        cwd=ROOT,
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    web = subprocess.Popen(
        ["npm", "run", "dev", "--", "--host", "127.0.0.1", "--port", str(args.web_port)],
        cwd=ROOT / "apps" / "web",
        env=os.environ.copy(),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    def shutdown() -> None:
        api.terminate()
        web.terminate()

    signal.signal(signal.SIGINT, lambda *_: shutdown())
    api_base = f"http://127.0.0.1:{args.api_port}"
    web_url = f"http://127.0.0.1:{args.web_port}/#/home"
    try:
        for _ in range(40):
            try:
                _http_json(f"{api_base}/healthz", timeout=1)
                break
            except Exception:
                time.sleep(0.25)
        else:
            print("API did not start", file=sys.stderr)
            shutdown()
            return 1
        print(f"API ready: {api_base}")
        print(f"Open the demo in your browser: {web_url}")
        if not args.no_browser:
            import webbrowser

            webbrowser.open(web_url)

        started = time.monotonic()
        last_phase = None
        while time.monotonic() - started < args.max_seconds:
            try:
                status = _http_json(f"{api_base}/api/stream/status", timeout=2)
                phase = status.get("demo_phase")
                if phase != last_phase:
                    print(
                        f"[{status.get('position_s', 0):6.1f}s] "
                        f"phase={phase} windows={status.get('windows')} "
                        f"seals={status.get('evidence_seals')} "
                        f"faults={status.get('faults')}"
                    )
                    last_phase = phase
                if status.get("finished"):
                    print("Demo finished.")
                    break
            except Exception:
                pass
            time.sleep(2)
    finally:
        shutdown()
        api.wait(timeout=5)
        web.wait(timeout=5)

    event_logs = sorted((ROOT / "data" / "derived" / "stream").glob("*.events.jsonl"))
    print("Artifacts:")
    print(f"  event log: {event_logs[-1] if event_logs else 'n/a'}")
    print(f"  reports:   {ROOT / 'artifacts'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
