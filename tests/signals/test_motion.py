"""Motion estimator: idle vs walk, single-link degradation."""

from __future__ import annotations

from tests.signals.conftest import run_stream


def test_idle_motion_is_low(profile, signal_estimator) -> None:
    triplets = run_stream("idle", seed=3, duration=4.0, profile=profile, estimator=signal_estimator)
    assert triplets
    assert all(t.motion.value < 0.35 for t in triplets)
    assert all(t.motion.state in ("idle", "micro_motion") for t in triplets)


def test_walk_motion_is_high(profile, signal_estimator) -> None:
    triplets = run_stream(
        "walk_through",
        seed=4,
        duration=5.0,
        profile=profile,
        estimator=signal_estimator,
    )
    assert any(t.motion.value > 0.6 for t in triplets)
    assert any(t.motion.state in ("moving", "fast_change") for t in triplets)
    peak = max(t.motion.value for t in triplets)
    idle = run_stream("idle", seed=4, duration=4.0, profile=profile, estimator=signal_estimator)
    idle_max = max(t.motion.value for t in idle)
    assert peak > idle_max


def test_single_link_motion_still_available(profile, signal_estimator) -> None:
    triplets = run_stream(
        "walk_through",
        seed=5,
        duration=4.0,
        profile=profile,
        estimator=signal_estimator,
        keep_links=("rx-a",),
    )
    assert triplets
    assert any(t.motion.value > 0.5 for t in triplets)
    assert all(t.motion.confidence <= t.sensor_confidence_cap for t in triplets)
