"""Collector service: frame sources, pairing, raw recording, replay, CLI."""

from __future__ import annotations

from .base import FrameSource
from .mock_source import SCENARIOS, MockFrameSource
from .replay_source import ReplayFrameSource
from .serial_live import SerialLiveFrameSource

__version__ = "0.1.0"

__all__ = [
    "SCENARIOS",
    "FrameSource",
    "MockFrameSource",
    "ReplayFrameSource",
    "SerialLiveFrameSource",
    "__version__",
]
