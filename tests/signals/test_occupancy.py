"""Occupancy estimator: ordinal monotonicity and motion freeze."""

from __future__ import annotations

from tests.signals.conftest import run_stream

_ORDINAL = {"low": 0, "medium": 1, "high": 2}


def _dominant(triplet) -> str:
    return triplet.occupancy_density.state


def test_idle_occupancy_is_low(profile, signal_estimator) -> None:
    triplets = run_stream("idle", seed=3, duration=4.0, profile=profile, estimator=signal_estimator)
    assert any(_dominant(t) == "low" for t in triplets)


def test_occupancy_levels_are_ordinal(profile, signal_estimator) -> None:
    states: dict[str, list[str]] = {}
    for level in ("low", "medium", "high"):
        triplets = run_stream(
            f"occupancy_{level}",
            seed=7,
            duration=4.0,
            profile=profile,
            estimator=signal_estimator,
        )
        states[level] = [_dominant(t) for t in triplets]
    mediums = states["medium"]
    highs = states["high"]
    # Median ordinal index must increase with the true level.
    medians = {
        level: sorted(_ORDINAL[state] for state in values)[len(values) // 2]
        for level, values in states.items()
    }
    assert medians["low"] <= medians["medium"] <= medians["high"]
    assert any(state == "high" for state in highs)
    assert any(state == "medium" for state in mediums)


def test_fast_motion_freezes_occupancy(profile, signal_estimator) -> None:
    triplets = run_stream(
        "walk_through",
        seed=9,
        duration=5.0,
        profile=profile,
        estimator=signal_estimator,
    )
    assert any(
        t.occupancy_density.state == "unknown"
        and t.motion.value >= 0.5
        for t in triplets
    )


def test_single_link_occupancy_unknown(profile, signal_estimator) -> None:
    triplets = run_stream(
        "idle",
        seed=11,
        duration=4.0,
        profile=profile,
        estimator=signal_estimator,
        keep_links=("rx-a",),
    )
    assert all(t.occupancy_density.state == "unknown" for t in triplets)
    assert all(t.occupancy_density.confidence == 0.0 for t in triplets)
