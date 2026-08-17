"""Shared council test helpers (no fixtures)."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime

from wifi_contracts import (
    AgentClaim,
    DepthProbabilities,
    DepthZone,
    EvidencePacket,
    MotionSignal,
    OccupancyDensity,
    OccupancyProbabilities,
    SignalTriplet,
)
from wifi_contracts.mock_fixtures import build_evidence, build_triplets, build_windows
from wifi_council.config import CouncilConfig
from wifi_council.orchestrator import PROPOSE_ROLES, CouncilOrchestrator
from wifi_council.provider import MockAgentProvider

FIXED_NOW = datetime(2026, 8, 6, 12, 0, 0, tzinfo=UTC)


def make_triplet(
    *,
    motion_state: str = "moving",
    motion_value: float = 0.72,
    occupancy_state: str = "low",
    depth_state: str = "near",
    status: str = "ok",
    cap: float = 0.8,
) -> SignalTriplet:
    base = build_triplets()[1]
    return SignalTriplet(
        schema_version="1.0.0",
        session_id=base.session_id,
        window_id=base.window_id,
        source_mode=base.source_mode,
        started_at=base.started_at,
        ended_at=base.ended_at,
        motion=MotionSignal(
            value=motion_value,
            state=motion_state,
            confidence=cap,
        ),
        occupancy_density=OccupancyDensity(
            probabilities=OccupancyProbabilities(
                low=1.0 if occupancy_state == "low" else 0.0,
                medium=1.0 if occupancy_state == "medium" else 0.0,
                high=1.0 if occupancy_state == "high" else 0.0,
                unknown=1.0 if occupancy_state == "unknown" else 0.0,
            ),
            state=occupancy_state,
            confidence=0.0 if occupancy_state == "unknown" else cap,
        ),
        depth_zone=DepthZone(
            probabilities=DepthProbabilities(
                near=1.0 if depth_state == "near" else 0.0,
                mid=1.0 if depth_state == "mid" else 0.0,
                far=1.0 if depth_state == "far" else 0.0,
                unknown=1.0 if depth_state == "unknown" else 0.0,
            ),
            state=depth_state,
            confidence=0.0 if depth_state == "unknown" else cap,
        ),
        sensor_confidence_cap=cap,
        evidence_refs=[],
        status=status,
    )


def make_packet(
    *,
    sequence: int = 1,
    cycle_id: str = "cycle-0001",
    motion_state: str = "moving",
    motion_value: float = 0.72,
    occupancy_state: str = "low",
    depth_state: str = "near",
    status: str = "ok",
    cap: float = 0.8,
    depth_allowed: bool = True,
    quality_flags: list[str] | None = None,
    link_ids: tuple[str, ...] = ("rx-a", "rx-b"),
) -> EvidencePacket:
    triplet = make_triplet(
        motion_state=motion_state,
        motion_value=motion_value,
        occupancy_state=occupancy_state,
        depth_state=depth_state,
        status=status,
        cap=cap,
    )
    packet = build_evidence(triplet, build_windows()[1])
    updates: dict = {}
    if sequence != 1:
        updates["sequence"] = sequence
    if cycle_id != "cycle-0001":
        updates["cycle_id"] = cycle_id
    if not depth_allowed or link_ids != ("rx-a", "rx-b"):
        updates["topology"] = packet.topology.model_copy(
            update={
                "depth_output_allowed": depth_allowed,
                "link_ids": list(link_ids),
            }
        )
    if quality_flags is not None:
        updates["quality"] = packet.quality.model_copy(
            update={"quality_flags": list(quality_flags)}
        )
    if updates:
        packet = EvidencePacket.create(**packet.model_copy(update=updates).model_dump())
    return packet


def claim(
    packet: EvidencePacket,
    *,
    role: str = "feng_shui",
    proposition: str = "动态扰动与 moving 状态一致",
    stance: str = "supports",
    refs: list[str] | None = None,
    claim_id: str = "claim-test-01",
) -> AgentClaim:
    resolved = refs or [
        f"evidence://{packet.evidence_hash}/signals/motion/state"
    ]
    return AgentClaim(
        schema_version="agent-claim.v1",
        claim_id=claim_id,
        cycle_id=packet.cycle_id,
        agent_id=f"agent-{role}-test",
        agent_version="test",
        role=role,
        kind="observation",
        state="proposed",
        proposition=proposition,
        stance=stance,
        evidence_refs=resolved,
        falsification_test="可重复测量验证。",
        reasoning_summary="测试主张。",
    )


def run_cycle(
    packet: EvidencePacket,
    *,
    budget: int = 8,
    roles: tuple[str, ...] | None = None,
    misbehave: str = "none",
    now: datetime = FIXED_NOW,
):
    config = CouncilConfig(max_calls_per_cycle=budget)
    provider = MockAgentProvider(
        config,
        misbehave=misbehave,  # type: ignore[arg-type]
    )
    orchestrator = CouncilOrchestrator(
        provider,
        config,
        propose_roles=tuple(roles) if roles else PROPOSE_ROLES,  # type: ignore[arg-type]
    )
    return asyncio.run(orchestrator.run_cycle(packet, now=now))
