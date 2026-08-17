"""API configuration. Reads non-secret settings from the environment."""

from __future__ import annotations

import os
from pathlib import Path

from wifi_contracts import SourceMode

APP_VERSION = "0.1.0"
SERVICE_NAME = "wifi-spatial-council-api"
CONTRACTS_VERSION = "1.0.0"


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
