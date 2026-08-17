"""FramePairer: pairing, unmatched, late, duplicate, wrap, bounded wait."""

from __future__ import annotations

import asyncio

from wifi_collector.mock_source import MockFrameSource
from wifi_collector.pairing import FramePairer


async def _frame(link: str, seq: int):
    source = MockFrameSource(
        scenario="idle",
        seed=1,
        duration_s=0.2,
        real_time=False,
    )
    async for frame in source.frames():
        if frame.link_id == link and frame.seq == seq:
            return frame
    raise AssertionError("frame not found")


def test_in_order_pairing() -> None:
    async def check() -> None:
        pairer = FramePairer(timeout_s=0.05)
        slots = []
        for seq in range(3):
            slots.extend(await pairer.feed(await _frame("rx-a", seq)))
            slots.extend(await pairer.feed(await _frame("rx-b", seq)))
        assert len(slots) == 3
        assert all(slot.paired for slot in slots)
        assert pairer.counters.paired == 3
        assert pairer.counters.unmatched == 0

    asyncio.run(check())


def test_single_link_emits_unmatched_after_bounded_wait() -> None:
    async def check() -> None:
        pairer = FramePairer(timeout_s=0.05)
        slots = await pairer.feed(await _frame("rx-a", 0))
        assert slots == []  # waits for rx-b
        await asyncio.sleep(0.08)
        slots = await pairer.feed(await _frame("rx-a", 1))
        assert len(slots) == 1
        assert slots[0].seq == 0
        assert not slots[0].paired
        assert pairer.counters.unmatched == 1
        assert pairer.counters.expired == 1

    asyncio.run(check())


def test_duplicate_and_late_counted() -> None:
    async def check() -> None:
        pairer = FramePairer(timeout_s=0.05)
        slots = []
        slots.extend(await pairer.feed(await _frame("rx-a", 0)))
        slots = await pairer.feed(await _frame("rx-a", 0))  # duplicate
        assert slots == []
        assert pairer.counters.duplicate == 1
        slots.extend(await pairer.feed(await _frame("rx-b", 0)))
        assert len(slots) == 1
        slots = await pairer.feed(await _frame("rx-a", 1))
        slots = await pairer.feed(await _frame("rx-b", 1))
        assert len(slots) == 1
        slots = await pairer.feed(await _frame("rx-b", 0))  # late after emit
        assert slots == []
        assert pairer.counters.late == 1

    asyncio.run(check())


def test_seq_wrap_counted() -> None:
    async def check() -> None:
        pairer = FramePairer(timeout_s=0.05)
        await pairer.feed(await _frame("rx-a", 5))
        await pairer.feed(await _frame("rx-b", 5))
        await pairer.feed(await _frame("rx-a", 1))  # wrap
        assert pairer.counters.wrap == 1

    asyncio.run(check())


def test_drain_flushes_pending() -> None:
    async def check() -> None:
        pairer = FramePairer(timeout_s=5.0)
        await pairer.feed(await _frame("rx-a", 0))
        assert pairer.pending_count() == 1
        slots = await pairer.drain()
        assert len(slots) == 1
        assert not slots[0].paired
        assert pairer.pending_count() == 0

    asyncio.run(check())
