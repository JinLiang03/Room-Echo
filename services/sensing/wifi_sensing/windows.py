"""Online sliding windows; windows never include future frames."""

from __future__ import annotations

from dataclasses import dataclass

from .cleaning import CleanedFrame
from .config import FeatureConfig


@dataclass
class Window:
    start_ns: int
    end_ns: int
    frames: dict[str, list[CleanedFrame]]


class SlidingWindowBuffer:
    """Emits 2 s windows at a fixed stride as soon as they are complete.

    Window boundaries depend only on frame timestamps, so chunking cannot
    change the output (chunk-invariance is tested).
    """

    def __init__(self, config: FeatureConfig) -> None:
        self.config = config
        self._frames: dict[str, list[CleanedFrame]] = {}
        self._epoch_ns: int | None = None
        self._next_window_end_ns: int | None = None

    def reset(self) -> None:
        self._frames.clear()
        self._epoch_ns = None
        self._next_window_end_ns = None

    def push(self, frame: CleanedFrame) -> list[Window]:
        if self._epoch_ns is None:
            self._epoch_ns = frame.ts_ns
            self._next_window_end_ns = self._epoch_ns + self.config.window_ns
        self._frames.setdefault(frame.link_id, []).append(frame)

        emitted: list[Window] = []
        while (
            self._next_window_end_ns is not None
            and frame.ts_ns >= self._next_window_end_ns
        ):
            end_ns = self._next_window_end_ns
            start_ns = end_ns - self.config.window_ns
            snapshot: dict[str, list[CleanedFrame]] = {}
            for link_id, frames in self._frames.items():
                snapshot[link_id] = [
                    item
                    for item in frames
                    if start_ns <= item.ts_ns < end_ns
                ]
            emitted.append(Window(start_ns=start_ns, end_ns=end_ns, frames=snapshot))
            self._next_window_end_ns = end_ns + self.config.stride_ns

        # Drop frames older than the last emitted window (bounded memory).
        if emitted:
            keep_from = emitted[-1].start_ns
            for link_id in list(self._frames):
                self._frames[link_id] = [
                    item for item in self._frames[link_id] if item.ts_ns >= keep_from
                ]
        return emitted

    def flush(self) -> list[Window]:
        """Emit a final partial window at end-of-stream (best effort)."""
        if self._epoch_ns is None or self._next_window_end_ns is None:
            return []
        end_ns = self._next_window_end_ns
        start_ns = end_ns - self.config.window_ns
        snapshot = {
            link_id: [
                item
                for item in frames
                if start_ns <= item.ts_ns < end_ns
            ]
            for link_id, frames in self._frames.items()
        }
        self._frames.clear()
        self._epoch_ns = None
        self._next_window_end_ns = None
        return [Window(start_ns=start_ns, end_ns=end_ns, frames=snapshot)]
