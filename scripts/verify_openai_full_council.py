#!/usr/bin/env python3
"""Verify and record one public, full real-provider Council invocation.

The historical filename is retained for release-package compatibility. Use
``--provider deepseek`` for the competition deployment requested in 2026-08.
"""

from __future__ import annotations

import argparse
import json
import urllib.error
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


def _post_json(url: str, payload: dict[str, Any], timeout_s: float) -> dict[str, Any]:
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout_s) as response:
            body = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:500]
        raise RuntimeError(f"invoke failed with HTTP {exc.code}: {detail}") from exc
    return dict(json.loads(body))


def _sanitized_report(
    endpoint: str,
    reading: dict[str, Any],
    expected_provider: str,
) -> dict[str, Any]:
    cycle = reading.get("council_cycle") or {}
    result = cycle.get("result") or {}
    calls = cycle.get("calls") or []
    successful = [call for call in calls if call.get("status") == "ok"]
    phases = sorted({str(call.get("phase")) for call in successful})
    required = {"propose", "cross_examine", "synthesize"}
    if reading.get("provider") != expected_provider:
        raise RuntimeError(
            f"invoke response provider is not {expected_provider!r}"
        )
    if (
        len(successful) < 7
        or int(reading.get("real_model_calls", 0)) < 7
        or not required.issubset(phases)
        or not result
    ):
        raise RuntimeError("invoke response is not a complete Council cycle")
    if reading.get("status") != "ready":
        raise RuntimeError("provider invocation completed without technical status=ready")
    cycle_status = cycle.get("status")
    if reading.get("cycle_status") != cycle_status:
        raise RuntimeError("invoke response mixed technical and semantic status")
    display = float(result.get("display_confidence", 0.0))
    cap = float(result.get("sensor_confidence_cap", 0.0))
    if display > cap + 1e-9:
        raise RuntimeError("confidence invariant failed")

    return {
        "schema_version": "real-council-verification.v1",
        "verified_at": datetime.now(UTC).isoformat(),
        "endpoint": endpoint,
        "session_id": reading.get("session_id"),
        "source_mode": reading.get("source_mode"),
        "source_is_simulated": True,
        "provider": reading.get("provider"),
        "model": (reading.get("provider_health") or {}).get("model"),
        "provider_status": (reading.get("provider_health") or {}).get("status"),
        "technical_status": reading.get("status"),
        "real_model_calls": reading.get("real_model_calls"),
        "cycle_id": cycle.get("cycle_id"),
        "evidence_hash": cycle.get("evidence_hash"),
        "cycle_status": cycle_status,
        "successful_phases": phases,
        "calls": [
            {
                "role": call.get("role"),
                "phase": call.get("phase"),
                "model": call.get("model"),
                "status": call.get("status"),
                "latency_ms": call.get("latency_ms"),
                "input_tokens": call.get("input_tokens", 0),
                "output_tokens": call.get("output_tokens", 0),
            }
            for call in successful
        ],
        "result": {
            "status": result.get("status"),
            "headline": result.get("headline"),
            "display_confidence": display,
            "sensor_confidence_cap": cap,
        },
        "truth_boundary": reading.get("truth_boundary", []),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "base_url",
        help="Deployed origin, for example https://wifi-spatial-council-replay.onrender.com",
    )
    parser.add_argument(
        "--provider",
        choices=("openai", "deepseek"),
        default="openai",
        help="Expected server-side provider provenance",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
    )
    parser.add_argument("--timeout", type=float, default=180.0)
    args = parser.parse_args()
    endpoint = args.base_url.rstrip("/") + "/api/agent/invoke"
    reading = _post_json(
        endpoint,
        {"focus": "overview", "evidence_wait_timeout_s": 30.0},
        args.timeout,
    )
    report = _sanitized_report(endpoint, reading, args.provider)
    output = args.output or Path(
        f"artifacts/submission/{args.provider}-full-council-evidence.json"
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        "verified full Council: "
        f"provider={report['provider']} model={report['model']} "
        f"calls={report['real_model_calls']} output={output}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
