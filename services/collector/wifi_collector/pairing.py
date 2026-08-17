"""Dual-link pairing by TX sequence with bounded wait and counters."""

from __future__ import annotations

import time
from collections import deque
from dataclasses import dataclass, field

from wifi_contracts import NormalizedCsiFrame


@dataclass
class PairedSlot:
    seq: int
    frames: dict[str, NormalizedCsiFrame]
    paired: bool
    late: bool = False
    duplicate: bool = False


@dataclass
class PairCounters:
    received: int = 0
    paired: int = 0
    unmatched: int = 0
    late: int = 0
    duplicate: int = 0
    wrap: int = 0
    expired: int = 0

    def as_dict(self) -> dict[str, int]:
        return {
            "received": self.received,
            "paired": self.paired,
            "unmatched": self.unmatched,
            "late": self.late,
            "duplicate": self.duplicate,
            "wrap": self.wrap,
            "expired": self.expired,
        }


@dataclass
class _Pending:
    frames: dict[str, NormalizedCsiFrame] = field(default_factory=dict)
    enqueued_at: float = 0.0


class FramePairer:
    """Pairs frames from both links by TX seq.

    A pending seq is emitted as soon as both links arrive; otherwise it is
    released after ``timeout_s`` (bounded wait) and counted as unmatched.
    Late, duplicate, and wrap events are counted, never repaired.
    """

    def __init__(
        self,
        links: tuple[str, ...] = ("rx-a", "rx-b"),
        timeout_s: float = 0.2,
        late_window: int = 8192,
    ) -> None:
        self._links = links
        self._timeout_s = timeout_s
        self._pending: dict[int, _Pending] = {}
        self._emitted: deque[int] = deque(maxlen=late_window)
        self._last_seq: dict[str, int | None] = {link: None for link in links}
        self.counters = PairCounters()

    async def feed(self, frame: NormalizedCsiFrame) -> list[PairedSlot]:
        slots: list[PairedSlot] = []
        self.counters.received += 1

        link = frame.link_id
        last = self._last_seq.get(link)
        if last is not None and frame.seq < last:
            self.counters.wrap += 1
        self._last_seq[link] = frame.seq

        if frame.seq in self._emitted:
            self.counters.late += 1
            return slots

        pending = self._pending.get(frame.seq)
        if pending is None:
            pending = _Pending(enqueued_at=time.monotonic())
            self._pending[frame.seq] = pending
        if link in pending.frames:
            self.counters.duplicate += 1
            return slots
        pending.frames[link] = frame

        if len(pending.frames) == len(self._links):
            del self._pending[frame.seq]
            self.counters.paired += 1
            self._emitted.append(frame.seq)
            slots.append(
                PairedSlot(seq=frame.seq, frames=pending.frames, paired=True)
            )

        slots.extend(await self._expire_old())
        return slots

    async def drain(self) -> list[PairedSlot]:
        """Flush all pending slots (end of stream)."""
        now = time.monotonic()
        slots: list[PairedSlot] = []
        for seq, pending in list(self._pending.items()):
            if len(pending.frames) == len(self._links):
                del self._pending[seq]
                self.counters.paired += 1
                self._emitted.append(seq)
                slots.append(
                    PairedSlot(seq=seq, frames=pending.frames, paired=True)
                )
            elif now - pending.enqueued_at >= self._timeout_s:
                del self._pending[seq]
                slots.extend(self._emit_unmatched(seq, pending, expired=True))
        # Anything still pending is older than the stream; emit as unmatched.
        for seq, pending in list(self._pending.items()):
            del self._pending[seq]
            slots.extend(self._emit_unmatched(seq, pending, expired=True))
        return slots

    async def _expire_old(self) -> list[PairedSlot]:
        now = time.monotonic()
        slots: list[PairedSlot] = []
        for seq, pending in list(self._pending.items()):
            if now - pending.enqueued_at < self._timeout_s:
                continue
            del self._pending[seq]
            slots.extend(self._emit_unmatched(seq, pending, expired=True))
        return slots

    def _emit_unmatched(
        self,
        seq: int,
        pending: _Pending,
        *,
        expired: bool,
    ) -> list[PairedSlot]:
        self.counters.unmatched += 1
        if expired:
            self.counters.expired += 1
        self._emitted.append(seq)
        return [
            PairedSlot(
                seq=seq,
                frames=pending.frames,
                paired=False,
                late=False,
                duplicate=False,
            )
        ]

    def pending_count(self) -> int:
        return len(self._pending)
