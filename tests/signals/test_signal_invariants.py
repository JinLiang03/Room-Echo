"""Invariants and agent isolation for signal outputs."""

from __future__ import annotations

from hypothesis import given, settings
from hypothesis import strategies as st
from tests.signals.conftest import run_stream


def _assert_triplet_invariants(triplet) -> None:
    cap = triplet.sensor_confidence_cap
    assert 0.0 <= cap <= 1.0
    for confidence, state in (
        (triplet.motion.confidence, triplet.motion.state),
        (triplet.occupancy_density.confidence, triplet.occupancy_density.state),
        (triplet.depth_zone.confidence, triplet.depth_zone.state),
    ):
        assert 0.0 <= confidence <= cap
        if state == "unknown":
            assert confidence == 0.0
    for probabilities in (
        triplet.occupancy_density.probabilities,
        triplet.depth_zone.probabilities,
    ):
        values = probabilities.model_dump().values()
        assert abs(sum(values) - 1.0) <= 1e-6
        for value in values:
            assert 0.0 <= value <= 1.0
    # Agent fields never appear in the estimator output.
    dump = triplet.model_dump(mode="json")
    assert "agent" not in json_paths(dump)
    assert "agreement" not in json_paths(dump)


def json_paths(node, prefix: str = "") -> list[str]:
    paths = []
    if isinstance(node, dict):
        for key, value in node.items():
            path = f"{prefix}.{key}" if prefix else key
            paths.append(path)
            paths.extend(json_paths(value, path))
    elif isinstance(node, list):
        for index, value in enumerate(node):
            paths.extend(json_paths(value, f"{prefix}[{index}]"))
    return paths


@settings(max_examples=12, deadline=None)
@given(
    scenario=st.sampled_from(
        ["idle", "walk_through", "static_obstruction", "interference", "rx_dropout"]
    ),
    seed=st.integers(min_value=1, max_value=1000),
)
def test_proxy_signal_invariants_hold(profile, signal_estimator, scenario, seed) -> None:
    triplets = run_stream(
        scenario,
        seed=seed,
        duration=3.0,
        profile=profile,
        estimator=signal_estimator,
    )
    for triplet in triplets:
        _assert_triplet_invariants(triplet)
