"""Subcarrier maps, masks, and golden carrier indexing."""

from __future__ import annotations

from wifi_sensing.subcarriers import (
    build_mask,
    build_subcarrier_map,
    carrier_indices,
)


def test_canonical_ht20_64_carrier_order() -> None:
    indices = carrier_indices(128, 20)
    assert indices == list(range(-32, 0)) + list(range(1, 33))
    assert 0 not in indices
    assert len(indices) == 64


def test_generic_map_is_deterministic() -> None:
    assert carrier_indices(16, 20) == list(range(-4, 4))
    assert carrier_indices(14, 20) == list(range(-3, 4))  # odd -> DC included


def test_mask_removes_dc_and_guards() -> None:
    indices = carrier_indices(128, 20)
    mask = build_mask(indices, mask_dc=True, guard_carriers=1)
    assert mask[0] is False  # -32 guard
    assert mask[-1] is False  # +32 guard
    assert sum(mask) == 62
    no_dc = build_mask(indices, mask_dc=False, guard_carriers=0)
    assert all(no_dc)


def test_subcarrier_map_valid_positions() -> None:
    submap = build_subcarrier_map(
        128,
        20,
        mask_dc=True,
        guard_carriers=2,
    )
    assert submap.valid_count == 60
    assert submap.valid_indices[0] == -30
    assert submap.valid_indices[-1] == 30
    assert len(submap.valid_positions()) == 60
