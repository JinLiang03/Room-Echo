"""Shared council test fixtures."""

from __future__ import annotations

import pytest
from wifi_council.config import CouncilConfig


@pytest.fixture(scope="session")
def council_config() -> CouncilConfig:
    return CouncilConfig(max_calls_per_cycle=8)


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line(
        "markers",
        "openai_smoke: opt-in OpenAI provider integration test (not in CI)",
    )
