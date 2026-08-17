"""Evidence sealing: trigger, determinism, compactness, integrity."""

from __future__ import annotations

import asyncio

from wifi_collector.mock_source import MockFrameSource
from wifi_contracts import (
    DepthProbabilities,
    DepthZone,
    MotionSignal,
    OccupancyDensity,
    OccupancyProbabilities,
    SignalTriplet,
)
from wifi_sensing.config import FeatureConfig
from wifi_sensing.pipeline import FeaturePipeline
from wifi_sensing.signal_config import SignalConfig
from wifi_sensing.signal_evidence import EvidenceBuilder, EvidenceTrigger


def _window_and_triplet(profile, signal_estimator):
    async def run():
        source = MockFrameSource(
            scenario="idle",
            seed=2,
            duration_s=4.0,
            real_time=False,
            topology_hash=profile.topology_hash,
        )
        manifest = await source.open()
        pipeline = FeaturePipeline(FeatureConfig(), profile)
        signal_estimator.reset()
        window = None
        triplet = None
        async for frame in source.frames():
            for item in pipeline.transform([frame], manifest):
                window = item
                triplet = signal_estimator.estimate(item)
        await source.close()
        return window, triplet, manifest

    return asyncio.run(run())


def _mk(
    motion_state: str,
    occupancy_state: str,
    depth_state: str,
) -> SignalTriplet:
    from datetime import UTC, datetime

    now = datetime.now(UTC)
    return SignalTriplet(
        schema_version="1.0.0",
        session_id="s",
        window_id="w",
        source_mode="mock",
        started_at=now,
        ended_at=now,
        motion=MotionSignal(value=0.5, state=motion_state, confidence=0.5),
        occupancy_density=OccupancyDensity(
            probabilities=OccupancyProbabilities(
                low=0.25,
                medium=0.25,
                high=0.25,
                unknown=0.25,
            ),
            state=occupancy_state,
            confidence=0.5,
        ),
        depth_zone=DepthZone(
            probabilities=DepthProbabilities(
                near=0.25,
                mid=0.25,
                far=0.25,
                unknown=0.25,
            ),
            state=depth_state,
            confidence=0.5,
        ),
        sensor_confidence_cap=0.5,
        evidence_refs=[],
        status="ok",
    )


def test_trigger_seals_first_and_after_stable_change() -> None:
    trigger = EvidenceTrigger(SignalConfig())
    t0 = _mk("idle", "low", "near")
    t1 = _mk("micro_motion", "low", "near")
    t2 = _mk("moving", "low", "near")
    t3 = _mk("moving", "medium", "mid")
    assert trigger.should_seal(t0, None, now_s=1.0, last_seal_s=None)
    # Cooldown not reached: no seal even on a major transition.
    assert not trigger.should_seal(t1, t0, now_s=1.5, last_seal_s=1.0)
    assert not trigger.should_seal(t2, t1, now_s=1.8, last_seal_s=1.0)
    # Cooldown reached with a stable state change across three windows.
    assert trigger.should_seal(t3, t2, now_s=5.0, last_seal_s=1.0)


def test_evidence_hash_is_deterministic_and_compact(profile, signal_estimator) -> None:
    window, triplet, manifest = _window_and_triplet(profile, signal_estimator)
    assert window is not None and triplet is not None
    builder = EvidenceBuilder(profile, manifest)
    first = builder.build(triplet, window, sequence=1, cycle_id="cycle-0001")
    second = builder.build(triplet, window, sequence=1, cycle_id="cycle-0001")
    assert first.evidence_hash == second.evidence_hash
    assert first.verify_integrity()
    # Arrays are never embedded in the sealed packet.
    for link in first.window_summary.links.values():
        assert link.amplitude_median == []
        assert link.amplitude_mad == []
    # Evidence index holds scalars only.
    for value in first.evidence_index.values():
        assert isinstance(value.value, (float, int, str, bool))


def test_evidence_hash_changes_with_content(profile, signal_estimator) -> None:
    window, triplet, manifest = _window_and_triplet(profile, signal_estimator)
    builder = EvidenceBuilder(profile, manifest)
    original = builder.build(triplet, window, sequence=1, cycle_id="cycle-0001")
    changed = builder.build(
        triplet,
        window.model_copy(update={"window_id": "window-other"}),
        sequence=1,
        cycle_id="cycle-0001",
    )
    assert changed.evidence_hash != original.evidence_hash
