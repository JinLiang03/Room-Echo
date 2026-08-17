"""Cleaning: golden amplitude, invalid-word, centering, causal filters."""

from __future__ import annotations

import math
from collections import deque
from datetime import UTC, datetime

import numpy as np
from wifi_contracts import CsiQuality, NormalizedCsiFrame, SourceManifest
from wifi_sensing.cleaning import CleaningTransformer, amplitude_from_iq
from wifi_sensing.config import FeatureConfig
from wifi_sensing.subcarriers import build_subcarrier_map


def _frame(
    magnitudes: list[float],
    *,
    seq: int = 0,
    ts_ns: int = 0,
    link: str = "rx-a",
    first_word_invalid: bool = False,
) -> NormalizedCsiFrame:
    iq: list[int] = []
    if first_word_invalid:
        iq.extend([99, -99, 99, -99])  # invalid first four bytes
    for magnitude in magnitudes:
        iq.append(0)  # imaginary
        iq.append(max(1, min(127, round(magnitude))))  # real, int8 range
    return NormalizedCsiFrame(
        schema_version="1.0.0",
        session_id="s",
        source_mode="mock",
        link_id=link,
        rx_id=link,
        tx_id_hash="fnv1a64:0123456789abcdef",
        seq=seq,
        device_ts_us=ts_ns // 1000,
        host_ts_ns=ts_ns,
        channel=6,
        bandwidth_mhz=20,
        rssi_dbm=-60.0,
        noise_floor_dbm=-95.0,
        first_word_invalid=first_word_invalid,
        csi_iq=iq,
        quality=CsiQuality(parse_ok=True, sequence_gap=0, timestamp_monotonic=True),
    )


def _manifest() -> SourceManifest:
    return SourceManifest(
        schema_version="wifi-source.v1",
        session_id="s",
        source_mode="mock",
        session_started_at=datetime(2026, 8, 6, tzinfo=UTC),
        link_ids=["rx-a", "rx-b"],
        firmware_versions={},
        topology_hash="sha256:" + "a" * 64,
    )


def test_amplitude_golden() -> None:
    # real=100, imag=0 -> |z|=100 -> 40 dB
    assert math.isclose(amplitude_from_iq([0, 100]), 40.0, abs_tol=1e-9)
    # real=10 -> 20 dB
    assert math.isclose(amplitude_from_iq([0, 10]), 20.0, abs_tol=1e-9)
    # interleaved order is imaginary first, real second
    assert math.isclose(amplitude_from_iq([0, 100]), 40.0, abs_tol=1e-9)


def test_clean_removes_invalid_first_word() -> None:
    config = FeatureConfig()
    cleaner = CleaningTransformer(config)
    frame = _frame([100.0] * 64, first_word_invalid=True)
    cleaned = cleaner.clean(frame, _manifest())
    assert cleaned is not None
    assert len(cleaned.carrier_indices) == 64
    # First four bytes are dropped; the canonical HT20 map starts at -32.
    assert cleaned.carrier_indices[0] == -32


def test_clean_centers_common_mode() -> None:
    config = FeatureConfig()
    cleaner = CleaningTransformer(config)
    # Two frames: same integer shape, one x3 magnitude (9.54 dB common gain),
    # staying within int8 so rounding is exact and the common mode is precise.
    base = [round(30.0 + 6.0 * math.sin(i / 6.0)) for i in range(64)]
    shifted = [value * 3 for value in base]
    a = cleaner.clean(_frame(base, seq=0, ts_ns=0), _manifest())
    b = cleaner.clean(_frame(shifted, seq=1, ts_ns=1_000_000), _manifest())
    assert a is not None and b is not None
    np.testing.assert_allclose(a.amplitudes, b.amplitudes, atol=1e-6)


def test_online_filter_never_peeks_future() -> None:
    config = FeatureConfig(ema_alpha=0.5)

    def series(spike_at: int | None) -> list[np.ndarray]:
        cleaner = CleaningTransformer(config)
        outputs = []
        for index in range(30):
            magnitudes = [50.0 + 4.0 * math.sin(index / 2.0)] * 64
            if spike_at is not None and index == spike_at:
                magnitudes = [min(127.0, value + 70.0) for value in magnitudes]
            cleaned = cleaner.clean(
                _frame(magnitudes, seq=index, ts_ns=index * 1_000_000),
                _manifest(),
            )
            assert cleaned is not None
            outputs.append(cleaned.amplitudes.copy())
        return outputs

    no_spike = series(None)
    late_spike = series(29)  # spike in the LAST frame
    for index in range(29):
        np.testing.assert_allclose(late_spike[index], no_spike[index], atol=1e-9)


def test_vectorized_online_filter_matches_scalar_hampel_reference() -> None:
    """The replay-speed optimization preserves each carrier's causal math."""
    config = FeatureConfig(hampel_window=5, ema_alpha=0.4)
    cleaner = CleaningTransformer(config)
    seed_frame = _frame([50.0] * 64)
    assert cleaner.validate_frame(seed_frame, _manifest()) is None
    submap = build_subcarrier_map(
        len(seed_frame.csi_iq),
        20,
        mask_dc=config.mask_dc,
        guard_carriers=config.guard_carriers,
    )
    rng = np.random.default_rng(20260808)
    histories: dict[int, deque[float]] = {
        index: deque(maxlen=config.hampel_window) for index in submap.valid_indices
    }
    scalar_ema: dict[int, float] = {}

    for step in range(25):
        amplitudes = rng.normal(0.0, 2.0, len(submap.valid_indices))
        if step in {8, 17}:
            amplitudes[7] += 40.0
        expected = np.empty_like(amplitudes)
        for position, (index, original) in enumerate(
            zip(submap.valid_indices, amplitudes, strict=True)
        ):
            value = float(original)
            history = histories[index]
            history.append(value)
            if len(history) >= config.hampel_window:
                samples = np.asarray(history, dtype=np.float64)
                center = float(np.median(samples))
                mad = float(np.median(np.abs(samples - center)))
                if mad > 1e-9 and abs(value - center) > config.hampel_n_sigmas * mad:
                    value = center
            prior = scalar_ema.get(index, value)
            current = config.ema_alpha * value + (1.0 - config.ema_alpha) * prior
            scalar_ema[index] = current
            expected[position] = current

        actual = cleaner._apply_online_filters("rx-a", submap, amplitudes)
        np.testing.assert_allclose(actual, expected, atol=1e-12)
