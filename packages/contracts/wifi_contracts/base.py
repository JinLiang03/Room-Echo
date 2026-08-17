"""Shared contract primitives: source modes, versions, and validation helpers."""

from __future__ import annotations

import math
from typing import Literal

SourceMode = Literal["mock", "replay", "live"]

SCHEMA_BASE = "https://wifi-spatial-council.local/schemas"
CONTRACTS_VERSION = "1.0.0"
PROBABILITY_TOLERANCE = 1e-6
HASH_PATTERN = r"^sha256:[0-9a-f]{64}$"


def require_probability_sum(
    values: list[float],
    *,
    tolerance: float = PROBABILITY_TOLERANCE,
) -> None:
    """Raise unless values sum to 1 within tolerance (used by probability proxies)."""
    if not math.isclose(sum(values), 1.0, rel_tol=0.0, abs_tol=tolerance):
        raise ValueError(
            f"probability distribution must sum to 1 within {tolerance}, got {sum(values):.9f}"
        )
