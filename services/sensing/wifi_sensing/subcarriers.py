"""Subcarrier maps and masking (canonical HT20 layout)."""

from __future__ import annotations

from dataclasses import dataclass


def carrier_indices(csi_len: int, bandwidth_mhz: int = 20) -> list[int]:
    """Label each IQ pair with its subcarrier index.

    Canonical HT20 with 64 carriers follows ESP-IDF ordering:
    -32..-1 then 1..32 (DC index 0 excluded). Other lengths use a generic
    symmetric map so the pipeline stays deterministic.
    """
    carriers = csi_len // 2
    if bandwidth_mhz == 20 and carriers == 64:
        return list(range(-32, 0)) + list(range(1, 33))
    half = carriers // 2
    if carriers % 2 == 0:
        return list(range(-half, half))
    return list(range(-half, half + 1))


def build_mask(
    indices: list[int],
    *,
    mask_dc: bool,
    guard_carriers: int,
) -> list[bool]:
    """Mask DC and outermost guard carriers; True = usable."""
    max_abs = max(abs(index) for index in indices) if indices else 0
    mask: list[bool] = []
    for index in indices:
        if (mask_dc and index == 0) or (guard_carriers > 0 and abs(index) > max_abs - guard_carriers):
            mask.append(False)
        else:
            mask.append(True)
    return mask


@dataclass(frozen=True)
class SubcarrierMap:
    csi_len: int
    bandwidth_mhz: int
    indices: list[int]
    mask: list[bool]

    @property
    def valid_indices(self) -> list[int]:
        return [
            index
            for index, usable in zip(self.indices, self.mask, strict=True)
            if usable
        ]

    @property
    def valid_count(self) -> int:
        return sum(self.mask)

    def valid_positions(self) -> list[int]:
        """Positions (into the IQ pair array) that survive the mask."""
        return [
            position
            for position, usable in enumerate(self.mask)
            if usable
        ]


def build_subcarrier_map(
    csi_len: int,
    bandwidth_mhz: int,
    *,
    mask_dc: bool,
    guard_carriers: int,
) -> SubcarrierMap:
    indices = carrier_indices(csi_len, bandwidth_mhz)
    mask = build_mask(
        indices,
        mask_dc=mask_dc,
        guard_carriers=guard_carriers,
    )
    return SubcarrierMap(
        csi_len=csi_len,
        bandwidth_mhz=bandwidth_mhz,
        indices=indices,
        mask=mask,
    )
