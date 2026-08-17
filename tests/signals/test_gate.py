"""Quality gate: packet loss, interference, staleness."""

from __future__ import annotations

from tests.signals.conftest import run_stream


def test_packet_loss_degrades_within_two_windows(profile, signal_estimator) -> None:
    triplets = run_stream(
        "packet_loss",
        seed=21,
        duration=5.0,
        profile=profile,
        estimator=signal_estimator,
    )
    assert len(triplets) >= 2
    # Within the first two windows quality must drop to degraded/insufficient.
    assert any(t.status in ("degraded", "insufficient_signal") for t in triplets[:2])


def test_interference_reduces_quality(profile, signal_estimator) -> None:
    triplets = run_stream(
        "interference",
        seed=23,
        duration=5.0,
        profile=profile,
        estimator=signal_estimator,
    )
    assert any(t.status in ("degraded", "insufficient_signal") for t in triplets)


def test_stale_clears_previous_state(profile, signal_estimator) -> None:
    run_stream("walk_through", seed=25, duration=4.0, profile=profile, estimator=signal_estimator)
    stale = signal_estimator.estimate_stale(
        session_id="s",
        source_mode="replay",
    )
    assert stale.motion.state == "unknown"
    assert stale.occupancy_density.state == "unknown"
    assert stale.depth_zone.state == "unknown"
    assert stale.motion.confidence == 0.0
    assert stale.occupancy_density.confidence == 0.0
    assert stale.depth_zone.confidence == 0.0
    assert stale.sensor_confidence_cap == 0.0
    assert stale.status == "insufficient_signal"
