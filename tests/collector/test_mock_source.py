"""MockFrameSource: determinism, scenarios, pause/resume, health."""

from __future__ import annotations

import asyncio

from wifi_collector.mock_source import SCENARIOS, MockFrameSource
from wifi_contracts import NormalizedCsiFrame


async def _collect(source: MockFrameSource, limit: int | None = None) -> list[NormalizedCsiFrame]:
    frames: list[NormalizedCsiFrame] = []
    async for frame in source.frames():
        frames.append(frame)
        if limit is not None and len(frames) >= limit:
            break
    return frames


def test_all_scenarios_construct_and_open() -> None:
    async def check() -> None:
        for name in SCENARIOS:
            source = MockFrameSource(
                scenario=name,
                seed=7,
                duration_s=0.1,
                real_time=False,
            )
            manifest = await source.open()
            assert manifest.source_mode == "mock"
            assert set(manifest.link_ids) == {"rx-a", "rx-b"}
            await source.close()

    asyncio.run(check())


def test_same_seed_is_deterministic() -> None:
    async def collect() -> list[dict]:
        source = MockFrameSource(
            scenario="walk_through",
            seed=42,
            duration_s=0.2,
            real_time=False,
        )
        frames = await _collect(source)
        return [frame.model_dump(mode="json") for frame in frames]

    first = asyncio.run(collect())
    second = asyncio.run(collect())
    assert first == second
    assert len(first) > 0


def test_rx_dropout_drops_one_link_and_degrades_health() -> None:
    async def check() -> None:
        source = MockFrameSource(
            scenario="rx_dropout",
            seed=3,
            duration_s=1.0,
            real_time=False,
        )
        frames = await _collect(source)
        rx_b_seqs = {frame.seq for frame in frames if frame.link_id == "rx-b"}
        # Dropout window is 30%-70% of ticks: rx-b must have a real hole.
        assert 0 in rx_b_seqs and max(rx_b_seqs) > 60
        assert len(rx_b_seqs) < 80  # not the full tick range
        health = await source.health()
        assert health.status == "degraded"
        assert health.dropped_links == ["rx-b"]
        await source.close()

    asyncio.run(check())


def test_packet_loss_counts_drops_and_frames_valid() -> None:
    async def check() -> None:
        source = MockFrameSource(
            scenario="packet_loss",
            seed=11,
            duration_s=1.0,
            real_time=False,
        )
        frames = await _collect(source)
        assert len(frames) > 0
        assert source._counters["dropped"] > 0
        for frame in frames:
            NormalizedCsiFrame.model_validate(frame.model_dump(mode="json"))
        await source.close()

    asyncio.run(check())


def test_pause_resume_controls_yield() -> None:
    async def check() -> None:
        source = MockFrameSource(
            scenario="idle",
            seed=1,
            rate_hz=200,
            duration_s=0.5,
            real_time=True,
        )
        await source.pause()
        results: list[int] = []

        async def consume() -> None:
            async for frame in source.frames():
                results.append(frame.seq)

        task = asyncio.create_task(consume())
        await asyncio.sleep(0.1)
        assert results == []  # paused from the start: nothing yields

        await source.resume()
        for _ in range(100):
            if len(results) >= 2:
                break
            await asyncio.sleep(0.01)
        assert len(results) >= 2

        await source.pause()
        before = len(results)
        await asyncio.sleep(0.1)
        assert len(results) == before  # nothing yields while paused

        await source.resume()
        for _ in range(100):
            if len(results) > before:
                break
            await asyncio.sleep(0.01)
        assert len(results) > before
        await source.close()
        await task

    asyncio.run(check())
