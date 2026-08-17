"""Council configuration: budget, deadlines, models, and policy constants.

Every tunable that changes council behavior is versioned here so a replay
with the same config string reproduces the same debate (ADR 0005).
"""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class CouncilConfig:
    version: str = "council-v1"
    max_calls_per_cycle: int = 8
    agent_timeout_s: float = 8.0
    retry_attempts: int = 2
    cycle_deadline_s: float = 15.0
    seed: int = 0xC011EC1
    mock_template_version: str = "mock-council.v1"
    model: str = "gpt-4o-mini"
    policy_version: str = "policy-v1"
    material_penalty: float = 0.75
    blocking_penalty: float = 0.5
    cache_enabled: bool = True
    max_challenges_total: int = 12


def provider_from_env() -> str:
    """AGENT_PROVIDER=mock|openai; mock is the CI-safe default."""
    value = os.environ.get("AGENT_PROVIDER", "mock").strip().lower()
    if value not in {"mock", "openai"}:
        raise ValueError(f"AGENT_PROVIDER must be mock or openai, got {value!r}")
    return value


def model_from_env(config: CouncilConfig) -> str:
    """Model names come from environment/config and appear in provenance."""
    return os.environ.get("AGENT_COUNCIL_MODEL", config.model).strip()
