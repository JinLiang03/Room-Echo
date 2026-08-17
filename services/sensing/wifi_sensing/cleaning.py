"""Frame validation and online cleaning (never peeks into the future)."""

from __future__ import annotations

import math
from collections import deque
from dataclasses import dataclass, field

import numpy as np
from wifi_contracts import NormalizedCsiFrame, SourceManifest

from .config import FeatureConfig
from .subcarriers import SubcarrierMap, build_subcarrier_map


@dataclass
class CleanedFrame:
    link_id: str
    ts_ns: int
    seq: int
    amplitudes: np.ndarray  # dB, one value per valid carrier
    carrier_indices: list[int]


@dataclass
class _LinkState:
    carrier_indices: tuple[int, ...] | None = None
    hampel_history: deque[np.ndarray] = field(default_factory=deque)
    ema: np.ndarray | None = None


class CleaningTransformer:
    """Validates frames against the manifest and cleans IQ to amplitude dB.

    Transform-only (no fit): gain/common-mode is removed with per-frame
    robust centering (median across carriers), which is deterministic and
    requires no calibration data. Baseline normalization happens later via
    the calibration profile.
    """

    def __init__(self, config: FeatureConfig) -> None:
        self.config = config
        self._states: dict[str, _LinkState] = {}

    def reset(self) -> None:
        self._states.clear()

    def validate_frame(
        self,
        frame: NormalizedCsiFrame,
        manifest: SourceManifest | None,
    ) -> str | None:
        """Return a rejection reason, or None when the frame is usable."""
        cfg = self.config
        if frame.link_id not in self._states:
            if manifest is not None and frame.link_id not in manifest.link_ids:
                return f"link {frame.link_id!r} not in manifest"
            self._states[frame.link_id] = _LinkState()
        if frame.channel != cfg.expected_channel:
            return f"channel {frame.channel} != {cfg.expected_channel}"
        if frame.bandwidth_mhz != cfg.expected_bandwidth_mhz:
            return f"bandwidth {frame.bandwidth_mhz} != {cfg.expected_bandwidth_mhz}"
        if len(frame.csi_iq) < 2 or len(frame.csi_iq) % 2 != 0:
            return f"invalid csi length {len(frame.csi_iq)}"
        return None

    def clean(
        self,
        frame: NormalizedCsiFrame,
        manifest: SourceManifest | None = None,
    ) -> CleanedFrame | None:
        reason = self.validate_frame(frame, manifest)
        if reason is not None:
            return None

        iq = np.asarray(frame.csi_iq, dtype=np.int16)
        if frame.first_word_invalid:
            iq = iq[4:]  # ESP-IDF: first four bytes invalid
        if len(iq) % 2 != 0:
            iq = iq[:-1]
        if len(iq) < 2:
            return None

        submap = build_subcarrier_map(
            len(iq),
            frame.bandwidth_mhz,
            mask_dc=self.config.mask_dc,
            guard_carriers=self.config.guard_carriers,
        )
        if submap.valid_count < 2:
            return None

        imag = iq[0::2].astype(np.float64)
        real = iq[1::2].astype(np.float64)
        magnitudes = np.hypot(real, imag)
        amplitude_db = 20.0 * np.log10(magnitudes + 1e-9)

        positions = submap.valid_positions()
        amplitudes = amplitude_db[positions]
        # Robust common-mode removal: subtract the per-frame median so a
        # shared gain change does not shift every carrier.
        amplitudes = amplitudes - float(np.median(amplitudes))

        cleaned = self._apply_online_filters(
            frame.link_id,
            submap,
            amplitudes,
        )
        return CleanedFrame(
            link_id=frame.link_id,
            ts_ns=frame.host_ts_ns,
            seq=frame.seq,
            amplitudes=cleaned,
            carrier_indices=submap.valid_indices,
        )

    def _apply_online_filters(
        self,
        link_id: str,
        submap: SubcarrierMap,
        amplitudes: np.ndarray,
    ) -> np.ndarray:
        """Hampel (past+current window) then EMA; strictly causal."""
        state = self._states[link_id]
        cfg = self.config
        carrier_indices = tuple(submap.valid_indices)
        if (
            state.carrier_indices != carrier_indices
            or state.hampel_history.maxlen != cfg.hampel_window
        ):
            # A layout change is a new filter epoch: never align a carrier
            # with a history that belonged to another position.
            state.carrier_indices = carrier_indices
            state.hampel_history = deque(maxlen=cfg.hampel_window)
            state.ema = None

        # All carriers on one link advance together, so the per-carrier
        # Hampel filters are exactly equivalent to a time-by-carrier matrix.
        # Computing both medians by axis avoids hundreds of thousands of
        # tiny NumPy allocations during a two-minute replay.
        state.hampel_history.append(amplitudes.copy())
        filtered = amplitudes
        if len(state.hampel_history) >= cfg.hampel_window:
            values = np.stack(state.hampel_history, axis=0)
            centers = np.median(values, axis=0)
            deviations = np.median(np.abs(values - centers), axis=0)
            outliers = (deviations > 1e-9) & (
                np.abs(amplitudes - centers) > cfg.hampel_n_sigmas * deviations
            )
            filtered = np.where(outliers, centers, amplitudes)

        if state.ema is None:
            state.ema = filtered.copy()
        else:
            state.ema = (
                cfg.ema_alpha * filtered + (1.0 - cfg.ema_alpha) * state.ema
            )
        return state.ema.copy()


def amplitude_from_iq(iq: list[int]) -> float:
    """Reference amplitude for golden tests: 20*log10(|z| + 1e-9)."""
    if len(iq) < 2 or len(iq) % 2 != 0:
        raise ValueError("IQ must be even-length")
    imag = float(iq[0])
    real = float(iq[1])
    return 20.0 * math.log10(math.hypot(real, imag) + 1e-9)
