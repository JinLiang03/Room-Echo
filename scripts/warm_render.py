#!/usr/bin/env python3
"""Pre-warm a public Render Replay service before a live demonstration.

Render Free web services can sleep after inactivity. This command only waits
for the existing health endpoint to become ready; it never invokes a model and
does not pretend to remove the platform-level sleep policy.
"""

from __future__ import annotations

import argparse
import json
import time
import urllib.error
import urllib.request
from typing import Any


def _health(url: str, timeout_s: float) -> tuple[int, str]:
    request = urllib.request.Request(
        url.rstrip("/") + "/healthz",
        headers={"User-Agent": "wifi-spatial-council-warmup/1.0"},
        method="GET",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout_s) as response:
            payload: dict[str, Any] = json.loads(response.read().decode("utf-8"))
            return response.status, str(payload.get("status", "unknown"))
    except urllib.error.HTTPError as exc:
        return exc.code, "http_error"
    except (TimeoutError, urllib.error.URLError, json.JSONDecodeError):
        return 0, "unreachable"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("url", help="Render service origin, e.g. https://...onrender.com")
    parser.add_argument("--timeout-s", type=float, default=150.0)
    parser.add_argument("--poll-interval-s", type=float, default=5.0)
    args = parser.parse_args()
    if args.timeout_s <= 0 or args.poll_interval_s <= 0:
        parser.error("--timeout-s and --poll-interval-s must be positive")

    started = time.monotonic()
    last_status = "unreachable"
    while time.monotonic() - started < args.timeout_s:
        http_status, health_status = _health(args.url, min(30.0, args.poll_interval_s * 2))
        last_status = f"http={http_status or 'timeout'} health={health_status}"
        if http_status == 200 and health_status == "ok":
            elapsed = time.monotonic() - started
            print(f"Render service ready after {elapsed:.1f}s ({args.url.rstrip('/')})")
            return 0
        time.sleep(args.poll_interval_s)

    print(f"Render service did not become ready within {args.timeout_s:.0f}s: {last_status}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
