"""Scheduler: retries, timeouts, offline fallback, out-of-order cycles."""

from __future__ import annotations

import asyncio

from _helpers import FIXED_NOW, make_packet
from wifi_council.audit import CouncilStore
from wifi_council.config import CouncilConfig
from wifi_council.orchestrator import CouncilOrchestrator
from wifi_council.provider import MockAgentProvider, OpenAIAgentProvider
from wifi_council.scheduler import CouncilScheduler


class FlakyProvider(MockAgentProvider):
    """Times out once per propose role, then succeeds."""

    def __init__(self, config: CouncilConfig) -> None:
        super().__init__(config)
        self._failed: set[str] = set()

    async def propose(self, role, packet, prompt):
        if role not in self._failed:
            self._failed.add(role)
            raise TimeoutError("simulated timeout")
        return await super().propose(role, packet, prompt)


class SlowOrchestrator(CouncilOrchestrator):
    async def run_cycle(self, packet, *, now=None):
        await asyncio.sleep(0.5)
        return await super().run_cycle(packet, now=now)


def test_retry_on_timeout_records_two_attempts() -> None:
    config = CouncilConfig(max_calls_per_cycle=12, agent_timeout_s=0.2)
    orchestrator = CouncilOrchestrator(FlakyProvider(config), config)
    detail = asyncio.run(orchestrator.run_cycle(make_packet(), now=FIXED_NOW))
    timeout_records = [record for record in detail.calls if record.status == "timeout"]
    assert timeout_records
    for record in timeout_records:
        assert record.attempts == 1
    ok_retries = [record for record in detail.calls if record.status == "ok" and record.attempts == 2]
    assert ok_retries, "timeouts must be retried once"
    assert len({claim.role for claim in detail.claims}) == 5


def test_all_provider_offline_returns_baseline() -> None:
    config = CouncilConfig(max_calls_per_cycle=8)
    provider = OpenAIAgentProvider(config, api_key=None)
    orchestrator = CouncilOrchestrator(provider, config)
    detail = asyncio.run(orchestrator.run_cycle(make_packet(), now=FIXED_NOW))
    assert detail.result is not None
    assert all(record.status == "offline" for record in detail.calls)
    assert detail.result.headline == "讨论不可用"


def test_cycle_deadline_produces_audited_baseline() -> None:
    config = CouncilConfig(max_calls_per_cycle=8, cycle_deadline_s=0.1)
    store = CouncilStore()
    scheduler = CouncilScheduler(
        SlowOrchestrator(MockAgentProvider(config), config),
        store,
        config,
    )
    async def submit_and_wait():
        scheduler.submit(make_packet(sequence=1))
        return await scheduler.wait_idle(timeout_s=5.0)

    assert asyncio.run(submit_and_wait())
    current = store.current
    assert current is not None
    assert current.status == "ambiguous"
    assert current.result is not None
    assert "cycle_deadline_exceeded" in current.result.limitations


def test_out_of_order_cycles_never_overwrite_current() -> None:
    config = CouncilConfig(max_calls_per_cycle=8)
    store = CouncilStore()
    scheduler = CouncilScheduler(
        CouncilOrchestrator(MockAgentProvider(config), config),
        store,
        config,
    )
    first = make_packet(sequence=1, cycle_id="cycle-0001")
    newer = make_packet(sequence=3, cycle_id="cycle-0003")
    older = make_packet(sequence=2, cycle_id="cycle-0002")

    async def run_scheduler():
        scheduler.submit(first)
        scheduler.submit(newer)  # replaces the pending slot
        scheduler.submit(older)  # ignored: not the latest pending
        assert scheduler.pending_sequence == 3
        return await scheduler.wait_idle(timeout_s=10.0)

    assert asyncio.run(run_scheduler())
    assert store.current is not None
    assert store.current.cycle_id == newer.cycle_id
    # A stale cycle finishing late cannot overwrite the newer snapshot.
    stale_detail = asyncio.run(
        CouncilOrchestrator(MockAgentProvider(config), config).run_cycle(
            older,
            now=FIXED_NOW,
        )
    )
    assert store.commit(stale_detail, 2) is False
    assert store.current.cycle_id == newer.cycle_id


def test_default_budget_never_exceeds_eight() -> None:
    config = CouncilConfig()
    assert config.max_calls_per_cycle == 8
    orchestrator = CouncilOrchestrator(MockAgentProvider(config), config)
    detail = asyncio.run(orchestrator.run_cycle(make_packet(), now=FIXED_NOW))
    assert len(detail.calls) <= 8
