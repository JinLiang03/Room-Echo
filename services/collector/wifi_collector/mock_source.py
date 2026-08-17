"""Deterministic mock frame source with fixed-seed scenarios."""

from __future__ import annotations

import asyncio
import math
import random
from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Literal

from wifi_contracts import CsiQuality, NormalizedCsiFrame, SourceHealth, SourceManifest

MOCK_RATE_HZ = 100
LINK_IDS = ("rx-a", "rx-b")
TX_ID_HASH = "fnv1a64:0123456789abcdef"
CHANNEL = 6


@dataclass(frozen=True)
class MockScenario:
    name: str
    packet_loss: float = 0.0
    dropout_link: str | None = None
    dropout_start_frac: float = 0.3
    dropout_end_frac: float = 0.7
    interference: bool = False
    motion_peak: float = 0.0
    obstruction_db: float = 0.0
    rx_b_shape_db: float = 0.0
    scripted: bool = False


SCENARIOS: dict[str, MockScenario] = {
    "idle": MockScenario(name="idle", motion_peak=0.05),
    "walk_through": MockScenario(name="walk_through", motion_peak=1.0),
    "static_obstruction": MockScenario(name="static_obstruction", motion_peak=0.1),
    "occupancy_low": MockScenario(name="occupancy_low", obstruction_db=4.0),
    "occupancy_medium": MockScenario(name="occupancy_medium", obstruction_db=10.0),
    "occupancy_high": MockScenario(name="occupancy_high", obstruction_db=18.0),
    "depth_1": MockScenario(name="depth_1"),
    "depth_2": MockScenario(name="depth_2", rx_b_shape_db=6.0),
    "depth_3": MockScenario(name="depth_3", rx_b_shape_db=12.0),
    "depth_4": MockScenario(name="depth_4", rx_b_shape_db=18.0),
    "depth_5": MockScenario(name="depth_5", rx_b_shape_db=24.0),
    "interference": MockScenario(
        name="interference",
        interference=True,
        packet_loss=0.35,
    ),
    "rx_dropout": MockScenario(
        name="rx_dropout",
        dropout_link="rx-b",
        dropout_start_frac=0.3,
        dropout_end_frac=0.7,
    ),
    "packet_loss": MockScenario(name="packet_loss", packet_loss=0.4),
    "demo_2min": MockScenario(name="demo_2min", scripted=True),
}


def _demo_phase(t_frac: float) -> dict[str, float | bool]:
    """Deterministic 120 s demo script (WEB_UX_SPEC two-minute timeline)."""
    # (start, end, start_params, end_params); parameters ramp linearly so the
    # estimators transition smoothly and never see hard steps.
    ramps: list[
        tuple[float, float, dict[str, float | bool], dict[str, float | bool]]
    ] = [
        # 1. idle baseline
        (
            0.00,
            0.16,
            {"motion": 0.04, "obstruction": 0.0, "shape": 0.0, "interference": False, "loss": 0.0},
            {"motion": 0.04, "obstruction": 0.0, "shape": 0.0, "interference": False, "loss": 0.0},
        ),
        # 2. far entry: motion + rx-b shape asymmetry grow (depth far)
            (
                0.16,
                0.33,
                {"motion": 0.04, "obstruction": 0.0, "shape": 0.0, "interference": False, "loss": 0.0},
                {"motion": 0.35, "obstruction": 0.0, "shape": 20.0, "interference": False, "loss": 0.0},
            ),
        # 3. approach: motion high, mild obstruction, mid depth
        (
            0.33,
            0.54,
            {"motion": 0.35, "obstruction": 0.0, "shape": 20.0, "interference": False, "loss": 0.0},
            {"motion": 0.45, "obstruction": 4.0, "shape": 16.0, "interference": False, "loss": 0.0},
        ),
        # 4. occupancy change: person stops near the link, obstruction high
        (
            0.54,
            0.70,
            {"motion": 0.45, "obstruction": 4.0, "shape": 16.0, "interference": False, "loss": 0.0},
            {"motion": 0.08, "obstruction": 18.0, "shape": 0.0, "interference": False, "loss": 0.0},
        ),
        # 5. ambiguous interference: correlated drift + mild loss
        (
            0.70,
            0.88,
            {"motion": 0.08, "obstruction": 18.0, "shape": 0.0, "interference": False, "loss": 0.0},
            {"motion": 0.50, "obstruction": 4.0, "shape": 8.0, "interference": True, "loss": 0.04},
        ),
        # 6. recovery: quiet idle
        (
            0.88,
            1.00,
            {"motion": 0.50, "obstruction": 4.0, "shape": 8.0, "interference": True, "loss": 0.04},
            {"motion": 0.03, "obstruction": 0.0, "shape": 0.0, "interference": False, "loss": 0.0},
        ),
    ]
    for start, end, start_params, end_params in ramps:
        if start <= t_frac < end:
            fraction = (t_frac - start) / max(end - start, 1e-9)
            return {
                key: float(start_params[key]) + (float(end_params[key]) - float(start_params[key])) * fraction
                for key in start_params
            }
    return {
        "motion": 0.03,
        "obstruction": 0.0,
        "shape": 0.0,
        "interference": False,
        "loss": 0.0,
    }


def _fake_hash(label: str) -> str:
    import hashlib

    return "sha256:" + hashlib.sha256(label.encode("utf-8")).hexdigest()


class MockFrameSource:
    """Deterministic scenario generator; yields frames for both links."""

    def __init__(
        self,
        *,
        scenario: str = "walk_through",
        seed: int = 0xC5F15EED,
        rate_hz: int = MOCK_RATE_HZ,
        duration_s: float = 10.0,
        session_id: str = "session-mock",
        real_time: bool = True,
        started_at: datetime | None = None,
        topology_hash: str | None = None,
    ) -> None:
        if scenario not in SCENARIOS:
            raise ValueError(f"unknown mock scenario: {scenario!r}")
        self.scenario = SCENARIOS[scenario]
        self.seed = seed
        self.rate_hz = rate_hz
        self.duration_s = duration_s
        self.session_id = session_id
        self.real_time = real_time
        self._topology_hash = topology_hash
        self._paused = asyncio.Event()
        self._paused.set()
        self._closed = False
        self._seek_s = 0.0
        self._step_remaining: int | None = None
        self._frame_count = 0
        self.rate = 1.0
        self._started_at = started_at or datetime.now(UTC)
        self._counters: dict[str, int] = {"generated": 0, "dropped": 0}

    async def open(self) -> SourceManifest:
        return SourceManifest(
            schema_version="wifi-source.v1",
            session_id=self.session_id,
            source_mode="mock",
            session_started_at=self._started_at,
            link_ids=list(LINK_IDS),
            firmware_versions={"csi_tx": "0.0.0-mock", "csi_rx": "0.0.0-mock"},
            topology_hash=self._topology_hash
            or _fake_hash("topology-two-rx-mock"),
            replay_ref=None,
        )

    async def frames(self) -> AsyncIterator[NormalizedCsiFrame]:
        rng = random.Random(self.seed)
        host_base_ns = int(self._started_at.timestamp() * 1_000_000_000)
        total_ticks = int(self.duration_s * self.rate_hz)
        interval_s = 1.0 / self.rate_hz

        for tick in range(total_ticks):
            if tick / self.rate_hz < self._seek_s:
                continue
            await self._paused.wait()
            if self._closed:
                return
            t_frac = tick / max(total_ticks - 1, 1)
            phase = _demo_phase(t_frac) if self.scenario.scripted else None
            loss = (
                float(phase["loss"])
                if phase is not None
                else self.scenario.packet_loss
            )
            for link_id in LINK_IDS:
                await self._paused.wait()
                if (
                    self._step_remaining is not None
                    and self._step_remaining <= 0
                ):
                    return
                if (
                    self.scenario.dropout_link == link_id
                    and self.scenario.dropout_start_frac <= t_frac
                    <= self.scenario.dropout_end_frac
                ):
                    self._counters["dropped"] += 1
                    continue
                if rng.random() < loss:
                    self._counters["dropped"] += 1
                    continue
                frame = self._frame_for(rng, tick, t_frac, link_id, host_base_ns)
                self._counters["generated"] += 1
                self._frame_count += 1
                if self._step_remaining is not None:
                    self._step_remaining -= 1
                yield frame
            if self.real_time:
                await asyncio.sleep(interval_s / max(0.25, self.rate))

    def _frame_for(
        self,
        rng: random.Random,
        tick: int,
        t_frac: float,
        link_id: str,
        host_base_ns: int,
    ) -> NormalizedCsiFrame:
        phase = _demo_phase(t_frac) if self.scenario.scripted else None
        if phase is not None:
            motion = float(phase["motion"])
            interference = bool(phase["interference"])
            obstruction_db = float(phase["obstruction"])
            shape_db = float(phase["shape"])
        else:
            motion = self.scenario.motion_peak * max(0.0, 1.0 - abs(t_frac - 0.5) * 2)
            interference = self.scenario.interference
            obstruction_db = self.scenario.obstruction_db
            shape_db = self.scenario.rx_b_shape_db
        rssi = -60.0 - motion * 4.0 + (rng.uniform(-2, 2) if interference else 0.0)
        noise = -95.0 + (rng.uniform(-4, 4) if interference else rng.uniform(-1, 1))
        device_ts_us = int(tick * 1_000_000 / self.rate_hz)
        iq = []
        for sub in range(64):
            base = 32 + 24 * (sub / 64.0)
            pattern = 0.0
            if obstruction_db or self.scenario.name == "static_obstruction":
                pattern += (obstruction_db or 12.0) * math.sin(
                    2 * math.pi * sub / 12.0
                )
            if (
                not obstruction_db
                and self.scenario.name != "static_obstruction"
            ) or (phase is not None and motion > 0.05):
                # Walk/interference: time-varying multipath pattern whose phase
                # moves with the tick -> large frame-to-frame carrier changes.
                pattern += (
                    motion
                    * 30.0
                    * math.sin(2 * math.pi * sub / 16.0 + tick * 0.35)
                )
            if link_id == "rx-b":
                pattern += shape_db * math.sin(2 * math.pi * sub / 8.0)
            jitter = rng.uniform(-1.5, 1.5)
            if self.scenario.interference:
                # Slow correlated drift survives robust cleaning but raises
                # low-band/variance indicators (interference, not motion).
                jitter = rng.uniform(-1.5, 1.5) + 8.0 * math.sin(
                    2 * math.pi * sub / 7.0 + tick * 0.02
                )
            amp = base + pattern + jitter
            iq.append(max(-128, min(127, int(amp))))
            iq.append(max(-128, min(127, int(amp * 0.5))))
        return NormalizedCsiFrame(
            schema_version="1.0.0",
            session_id=self.session_id,
            source_mode="mock",
            link_id=link_id,
            rx_id=link_id,
            tx_id_hash=TX_ID_HASH,
            seq=tick,
            device_ts_us=device_ts_us,
            host_ts_ns=device_ts_us * 1000,
            channel=CHANNEL,
            bandwidth_mhz=20,
            rssi_dbm=round(rssi, 2),
            noise_floor_dbm=round(noise, 2),
            rate=None,
            secondary_channel=None,
            ltf_mode=None,
            first_word_invalid=False,
            csi_iq=iq,
            quality=CsiQuality(
                parse_ok=True,
                sequence_gap=0,
                timestamp_monotonic=True,
                notes=[],
            ),
        )

    async def pause(self) -> None:
        self._paused.clear()

    async def resume(self) -> None:
        self._paused.set()

    async def close(self) -> None:
        self._closed = True
        self._paused.set()

    def seek(self, seconds: float) -> None:
        self._seek_s = max(0.0, seconds)

    def step(self, count: int) -> None:
        self._step_remaining = max(1, count)

    @property
    def is_paused(self) -> bool:
        return not self._paused.is_set()

    async def health(self) -> SourceHealth:
        status: Literal["ok", "degraded"] = "ok"
        degraded = list(LINK_IDS)
        if self.scenario.dropout_link is not None or self.scenario.packet_loss > 0:
            status = "degraded"
        dropped_links = (
            [self.scenario.dropout_link]
            if self.scenario.dropout_link is not None
            else []
        )
        active = [link for link in LINK_IDS if link not in dropped_links]
        return SourceHealth(
            schema_version="source-health.v1",
            session_id=self.session_id,
            source_mode="mock",
            status=status,
            active_links=active,
            degraded_links=degraded if status == "degraded" else [],
            dropped_links=dropped_links,
            counters=dict(self._counters),
            epoch=0,
            updated_at=datetime.now(UTC),
        )
