"""Calibration profiles: deterministic fit, unstable carrier drop."""

from __future__ import annotations

import numpy as np
from wifi_sensing.calibration import demo_profile, fit_profile
from wifi_sensing.cleaning import CleanedFrame
from wifi_sensing.config import FeatureConfig


def _frames(n: int, noisy_carrier: int | None = None) -> list[CleanedFrame]:
    rng = np.random.default_rng(7)
    frames = []
    for index in range(n):
        amplitudes = 40.0 + 5.0 * np.sin(np.arange(64) / 6.0)
        amplitudes = amplitudes + rng.normal(0, 0.2, size=64)
        if noisy_carrier is not None:
            amplitudes[noisy_carrier] += rng.normal(0, 10.0, size=1)[0]
        frames.append(
            CleanedFrame(
                link_id="rx-a",
                ts_ns=index * 1_000_000,
                seq=index,
                amplitudes=amplitudes,
                carrier_indices=list(range(-32, 0)) + list(range(1, 33)),
            )
        )
    return frames


def test_fit_profile_is_deterministic() -> None:
    config = FeatureConfig()
    a = fit_profile(
        _frames(100),
        config,
        profile_id="p",
        topology_hash="sha256:" + "a" * 64,
    )
    b = fit_profile(
        _frames(100),
        config,
        profile_id="p",
        topology_hash="sha256:" + "a" * 64,
    )
    # checksum covers fitted_at, so both legitimately differ run-to-run.
    assert a.model_dump(exclude={"fitted_at", "checksum"}) == b.model_dump(
        exclude={"fitted_at", "checksum"}
    )
    assert a.valid_count >= config.min_valid_carriers


def test_unstable_carrier_is_dropped() -> None:
    config = FeatureConfig(drop_unstable_frac=0.2)
    profile = fit_profile(
        _frames(200, noisy_carrier=10),
        config,
        profile_id="p",
        topology_hash="sha256:" + "a" * 64,
    )
    assert profile.valid_carriers[10] is False
    assert profile.valid_count == 64 - round(0.2 * 64)


def test_demo_profile_is_fixed_and_complete() -> None:
    config = FeatureConfig()
    a = demo_profile(config, "sha256:" + "b" * 64)
    b = demo_profile(config, "sha256:" + "b" * 64)
    assert a.model_dump() == b.model_dump()
    assert a.valid_count == 64
    assert a.source == "demo"
