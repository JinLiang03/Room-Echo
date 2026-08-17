"""API configuration. Reads non-secret settings from the environment."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Literal, cast

from wifi_contracts import SourceMode

APP_VERSION = "0.1.0"
SERVICE_NAME = "wifi-spatial-council-api"
CONTRACTS_VERSION = "1.0.0"
PUBLIC_REPLAY_BUNDLE_ID = "demo_2min"
PUBLIC_REPLAY_FORBIDDEN_DETAIL = (
    "public Replay is read-only; session and fault controls are disabled"
)


def get_app_mode() -> SourceMode:
    """Return APP_MODE validated against the three supported source modes."""
    value = os.environ.get("APP_MODE", "mock").strip().lower()
    if value == "mock":
        return "mock"
    if value == "replay":
        return "replay"
    if value == "live":
        return "live"
    raise ValueError(f"APP_MODE must be one of mock|replay|live, got {value!r}")


APP_MODE: SourceMode = get_app_mode()


def get_scenario() -> str:
    """SCENARIO selects the mock/replay demo source (default walk_through)."""
    return os.environ.get("SCENARIO", "walk_through").strip()


def get_rx_ports() -> dict[str, str]:
    """RX_PORTS=rx-a=/dev/ttyUSB0,rx-b=/dev/ttyUSB1 (live mode only)."""
    ports: dict[str, str] = {}
    for item in os.environ.get("RX_PORTS", "").split(","):
        if "=" in item:
            key, value = item.split("=", 1)
            if key in ("rx-a", "rx-b"):
                ports[key] = value.strip()
    return ports


def get_live_topology_hash() -> str | None:
    """Explicit calibrated topology identity required by Live mode."""
    value = os.environ.get("LIVE_TOPOLOGY_HASH", "").strip().lower()
    return value or None


def get_calibration_profile_path() -> Path | None:
    """Optional server-side path to the active calibration profile."""
    value = os.environ.get("CALIBRATION_PROFILE", "").strip()
    return Path(value) if value else None


def demo_autostart() -> bool:
    """DEMO_AUTOSTART=1 starts the configured demo session on API startup."""
    return os.environ.get("DEMO_AUTOSTART", "0") == "1"


def demo_loop() -> bool:
    """DEMO_LOOP=1 repeats an explicitly autostarted replay/mock demo."""
    return os.environ.get("DEMO_LOOP", "0") == "1"


def serve_web() -> bool:
    """SERVE_WEB=1 serves the built Vite application from FastAPI."""
    return os.environ.get("SERVE_WEB", "0") == "1"


def public_replay() -> bool:
    """PUBLIC_REPLAY=1 enables the fail-closed, read-only competition mode."""
    return os.environ.get("PUBLIC_REPLAY", "0") == "1"


def public_openai_invoke() -> bool:
    """Backward-compatible alias for the real-provider invocation gate."""
    return public_real_provider_invoke()


def public_real_provider_invoke() -> bool:
    """Allow one cached, server-side real-provider Council invocation.

    This is deliberately separate from ``AGENT_PROVIDER``. The continuously
    looping presentation stays deterministic and inexpensive, while the
    evaluator-facing Agent entry point may execute one real, fully audited
    Council cycle when the server has an API key.
    """
    value = os.environ.get(
        "PUBLIC_REAL_PROVIDER_INVOKE",
        os.environ.get("PUBLIC_OPENAI_INVOKE", "0"),
    )
    return value == "1"


def real_agent_provider() -> Literal["openai", "deepseek"]:
    """Select the one-shot evaluator provider without changing the live loop."""
    value = os.environ.get("REAL_AGENT_PROVIDER", "openai").strip().lower()
    if value not in {"openai", "deepseek"}:
        raise ValueError(
            f"REAL_AGENT_PROVIDER must be openai or deepseek, got {value!r}"
        )
    return cast(Literal["openai", "deepseek"], value)
