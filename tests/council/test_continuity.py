"""Cross-cycle role continuity, bounded fan-out, and progress events."""

from __future__ import annotations

import asyncio
import time

from _helpers import FIXED_NOW, make_packet
from wifi_contracts import EvidencePacket
from wifi_council.config import CouncilConfig
from wifi_council.continuity import CouncilContinuityTracker
from wifi_council.orchestrator import CouncilOrchestrator
from wifi_council.outputs import ResponseOutput
from wifi_council.provider import MockAgentProvider, ProviderCall


def test_second_cycle_links_every_visible_role_to_prior_evidence() -> None:
    config = CouncilConfig(max_calls_per_cycle=10)
    orchestrator = CouncilOrchestrator(MockAgentProvider(config), config)
    first_packet = make_packet(sequence=1, cycle_id="cycle-0001")
    second_packet = make_packet(
        sequence=2,
        cycle_id="cycle-0002",
        motion_state="fast_change",
        motion_value=0.92,
        occupancy_state="high",
        depth_state="near",
    )

    async def run():
        first = await orchestrator.run_cycle(first_packet, now=FIXED_NOW)
        second = await orchestrator.run_cycle(second_packet, now=FIXED_NOW)
        return first, second

    first, second = asyncio.run(run())
    assert all(claim.continuity is not None for claim in first.claims)
    assert {claim.continuity.relation for claim in first.claims if claim.continuity} == {
        "initial"
    }
    for claim in second.claims:
        continuity = claim.continuity
        assert continuity is not None
        assert continuity.previous_cycle_id == first_packet.cycle_id
        assert continuity.previous_evidence_hash == first_packet.evidence_hash
        assert continuity.relation == "intensified"
        assert {"motion", "occupancy"} <= set(continuity.changed_signals)
        assert [step.phase for step in claim.analysis_steps][1] == "compare"
    assert second.challenges
    assert second.challenges[0].continuity is not None
    assert second.challenges[0].continuity.previous_cycle_id == first_packet.cycle_id
    assert second.result is not None and second.result.continuity is not None
    assert second.result.continuity.previous_cycle_id == first_packet.cycle_id


def test_five_specialists_use_one_parallel_wave_and_unique_call_ids() -> None:
    class DelayedProvider(MockAgentProvider):
        async def propose(self, role, packet, prompt):
            await asyncio.sleep(0.05)
            return await super().propose(role, packet, prompt)

    config = CouncilConfig(max_calls_per_cycle=10)
    orchestrator = CouncilOrchestrator(DelayedProvider(config), config)
    started = time.perf_counter()
    detail = asyncio.run(orchestrator.run_cycle(make_packet(), now=FIXED_NOW))
    elapsed = time.perf_counter() - started

    assert elapsed < 0.18, "five 50 ms proposers should not run serially"
    propose_calls = [record for record in detail.calls if record.phase == "propose"]
    assert len(propose_calls) == 5
    assert len({record.call_id for record in detail.calls}) == len(detail.calls)
    assert len(detail.calls) <= config.max_calls_per_cycle


def test_same_category_numeric_change_advances_the_next_view() -> None:
    config = CouncilConfig(max_calls_per_cycle=10)
    orchestrator = CouncilOrchestrator(MockAgentProvider(config), config)
    first = make_packet(motion_state="moving", motion_value=0.62)
    second = make_packet(
        sequence=2,
        cycle_id="cycle-0002",
        motion_state="moving",
        motion_value=0.82,
    )

    async def run():
        await orchestrator.run_cycle(first, now=FIXED_NOW)
        return await orchestrator.run_cycle(second, now=FIXED_NOW)

    detail = asyncio.run(run())
    continuity = detail.claims[0].continuity
    assert continuity is not None
    assert continuity.relation == "intensified"
    assert continuity.changed_signals == ["motion"]
    assert "0.62" in continuity.summary
    assert "0.82" in continuity.summary


def test_progress_sink_receives_only_policy_screened_claims() -> None:
    config = CouncilConfig(max_calls_per_cycle=10)
    events: list[tuple[str, dict]] = []
    provider = MockAgentProvider(config, misbehave="overreach")
    orchestrator = CouncilOrchestrator(
        provider,
        config,
        progress_sink=lambda event_type, payload: events.append((event_type, payload)),
    )
    detail = asyncio.run(orchestrator.run_cycle(make_packet(), now=FIXED_NOW))

    streamed_claims = [
        payload["claim"]
        for event_type, payload in events
        if event_type == "agent.claim"
    ]
    rejected_ids = {rejection.target_id for rejection in detail.rejections}
    assert rejected_ids
    assert all(claim["claim_id"] not in rejected_ids for claim in streamed_claims)
    assert any(event_type == "policy.rejection" for event_type, _ in events)


def test_invalid_response_never_streams_or_enters_next_cycle_memory() -> None:
    class UnsafeResponseProvider(MockAgentProvider):
        async def respond(self, packet, claim, challenges, prompt):
            return ProviderCall(
                value=ResponseOutput(
                    state="revised",
                    proposition="距离 3.2 米处检测到一个人",
                    reasoning_summary="故意构造的越界测试响应",
                ),
                model=self.model,
                latency_ms=1,
            )

    config = CouncilConfig(max_calls_per_cycle=10)
    events: list[tuple[str, dict]] = []
    orchestrator = CouncilOrchestrator(
        UnsafeResponseProvider(config),
        config,
        progress_sink=lambda event_type, payload: events.append((event_type, payload)),
    )
    first = asyncio.run(orchestrator.run_cycle(make_packet(), now=FIXED_NOW))
    rejected_ids = {rejection.target_id for rejection in first.rejections}
    assert rejected_ids
    assert all(
        payload["claim"]["claim_id"] not in rejected_ids
        for event_type, payload in events
        if event_type == "agent.response"
    )

    second = asyncio.run(
        orchestrator.run_cycle(
            make_packet(sequence=2, cycle_id="cycle-0002"),
            now=FIXED_NOW,
        )
    )
    rejected_role = next(
        claim.role for claim in first.claims if claim.claim_id in rejected_ids
    )
    next_claim = next(claim for claim in second.claims if claim.role == rejected_role)
    assert next_claim.continuity is not None
    assert next_claim.continuity.previous_record_id is None


def test_continuity_tracker_evicts_old_sessions() -> None:
    tracker = CouncilContinuityTracker(max_sessions=2)

    def for_session(index: int, *, sequence: int = 1) -> EvidencePacket:
        base = make_packet(
            sequence=sequence,
            cycle_id=f"cycle-{index:04d}-{sequence}",
        )
        return EvidencePacket.create(
            **base.model_copy(update={"session_id": f"session-{index}"}).model_dump()
        )

    for index in range(3):
        tracker.commit(for_session(index), [], [], None)

    evicted_context = tracker.context(for_session(0, sequence=2), "architecture")
    retained_context = tracker.context(for_session(2, sequence=2), "architecture")
    assert evicted_context.record.relation == "initial"
    assert retained_context.record.relation == "steady"
