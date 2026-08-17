"""Bounded, cached execution of one real-provider Council cycle.

The presentation stream deliberately remains deterministic.  This module is
the only path allowed to spend model tokens in the public demo: it consumes a
compact, already-sealed ``EvidencePacket``, runs one full Council, caches the
result for the life of the process, and never exposes credentials or raw CSI.
"""

from __future__ import annotations

import asyncio
import os
from collections.abc import Callable
from dataclasses import dataclass
from time import perf_counter

from wifi_contracts import (
    CouncilCycleDetail,
    CouncilUsageSummary,
    EvidencePacket,
    ProviderHealth,
)
from wifi_council.config import CouncilConfig
from wifi_council.provider_types import AgentProvider
from wifi_council.runtime import CouncilRuntime, build_provider

from .config import public_real_provider_invoke, real_agent_provider


class RealProviderUnavailable(RuntimeError):
    """The real-provider gate is disabled, unconfigured, or lacks evidence."""


class RealProviderIncomplete(RuntimeError):
    """The provider returned without a complete auditable Council result."""


@dataclass(frozen=True)
class VerifiedCouncilRun:
    packet: EvidencePacket
    detail: CouncilCycleDetail
    provider_health: ProviderHealth
    usage: CouncilUsageSummary
    elapsed_ms: float


ProviderFactory = Callable[[CouncilConfig], AgentProvider]


def _configured_provider(config: CouncilConfig) -> AgentProvider:
    name = real_agent_provider()
    if name == "deepseek":
        return build_provider(config, "deepseek")
    return build_provider(config, "openai")


class VerifiedCouncilRunner:
    """Run one cached success with a small cap on paid attempts per process."""

    def __init__(
        self,
        provider_factory: ProviderFactory = _configured_provider,
        *,
        max_attempts_per_process: int = 2,
    ) -> None:
        if max_attempts_per_process < 1:
            raise ValueError("max_attempts_per_process must be positive")
        self._provider_factory = provider_factory
        self._max_attempts_per_process = max_attempts_per_process
        self._attempts = 0
        self._lock = asyncio.Lock()
        self._cached: VerifiedCouncilRun | None = None

    async def run(self, packet: EvidencePacket) -> VerifiedCouncilRun:
        if not public_real_provider_invoke():
            raise RealProviderUnavailable(
                "real-provider invocation is disabled on this deployment"
            )
        if packet.signals.status != "ok" or not packet.verify_integrity():
            raise RealProviderUnavailable(
                "no integrity-verified evidence packet has passed the sensing gate"
            )

        async with self._lock:
            if self._cached is not None:
                return self._cached
            timeout_s = min(
                180.0,
                max(
                    30.0,
                    float(
                        os.environ.get(
                            "REAL_COUNCIL_DEADLINE_S",
                            os.environ.get("OPENAI_COUNCIL_DEADLINE_S", "120"),
                        )
                    ),
                ),
            )
            config = CouncilConfig(
                max_calls_per_cycle=10,
                agent_timeout_s=min(45.0, max(8.0, timeout_s / 4.0)),
                retry_attempts=2,
                cycle_deadline_s=timeout_s,
                cache_enabled=True,
            )
            provider = self._provider_factory(config)
            health = provider.health()
            if provider.name not in {"openai", "deepseek"} or health.status != "ok":
                raise RealProviderUnavailable(
                    "server-side real Agent provider is not configured"
                )
            if self._attempts >= self._max_attempts_per_process:
                raise RealProviderUnavailable(
                    "real-provider attempt budget is exhausted for this server process"
                )
            self._attempts += 1

            runtime = CouncilRuntime(config, provider=provider)
            started = perf_counter()
            try:
                detail = await asyncio.wait_for(
                    runtime.orchestrator.run_cycle(packet),
                    timeout=timeout_s,
                )
            except TimeoutError as exc:
                raise RealProviderIncomplete(
                    "real-provider Council exceeded its bounded deadline"
                ) from exc
            elapsed_ms = round((perf_counter() - started) * 1000.0, 3)

            successful = [
                record for record in detail.calls if record.status in {"ok", "cache_hit"}
            ]
            real_calls = [record for record in detail.calls if record.status == "ok"]
            phases = {record.phase for record in successful}
            required_phases = {"propose", "cross_examine", "synthesize"}
            if (
                detail.result is None
                or len(real_calls) < 7
                or not required_phases.issubset(phases)
            ):
                raise RealProviderIncomplete(
                    "real-provider Council did not complete propose, challenge, and synthesis"
                )
            runtime.store.commit(detail, packet.sequence)
            run = VerifiedCouncilRun(
                packet=packet.model_copy(deep=True),
                detail=detail.model_copy(deep=True),
                provider_health=health,
                usage=runtime.store.usage_summary(),
                elapsed_ms=elapsed_ms,
            )
            self._cached = run
            return run


_verified_runner = VerifiedCouncilRunner()


def get_verified_runner() -> VerifiedCouncilRunner:
    return _verified_runner


def reset_verified_runner_for_testing(
    provider_factory: ProviderFactory = _configured_provider,
) -> VerifiedCouncilRunner:
    global _verified_runner
    _verified_runner = VerifiedCouncilRunner(provider_factory)
    return _verified_runner
