"""Depth estimator: monotonic zones, single-RX unknown, mismatch unknown."""

from __future__ import annotations

from tests.signals.conftest import run_stream

_ORDINAL = {"near": 0, "mid": 1, "far": 2}


def test_depth_points_are_monotonic(profile, signal_estimator) -> None:
    medians = []
    for point in range(1, 6):
        triplets = run_stream(
            f"depth_{point}",
            seed=13,
            duration=4.0,
            profile=profile,
            estimator=signal_estimator,
        )
        values = [_ORDINAL[t.depth_zone.state] for t in triplets]
        medians.append(sorted(values)[len(values) // 2])
    assert medians == sorted(medians)
    assert medians[0] <= 1
    assert medians[-1] >= 1


def test_single_rx_depth_always_unknown(profile, signal_estimator) -> None:
    triplets = run_stream(
        "depth_3",
        seed=17,
        duration=4.0,
        profile=profile,
        estimator=signal_estimator,
        keep_links=("rx-a",),
    )
    assert all(t.depth_zone.state == "unknown" for t in triplets)
    assert all(t.depth_zone.confidence == 0.0 for t in triplets)


def test_profile_mismatch_makes_signals_uncalibrated(profile, signal_estimator) -> None:
    from wifi_sensing.calibration import demo_profile
    from wifi_sensing.config import FeatureConfig

    mismatched = demo_profile(
        FeatureConfig(),
        "sha256:" + "f" * 64,
    )
    from wifi_sensing.signal_triplet import SignalEstimator

    estimator = SignalEstimator(signal_estimator.config, mismatched)
    triplets = run_stream(
        "idle",
        seed=19,
        duration=4.0,
        profile=mismatched,
        estimator=estimator,
        source_topology_hash="sha256:" + "e" * 64,
    )
    assert all(t.status == "uncalibrated" for t in triplets)
    assert all(t.occupancy_density.state == "unknown" for t in triplets)
    assert all(t.depth_zone.state == "unknown" for t in triplets)
