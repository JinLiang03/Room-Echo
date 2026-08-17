"""FrameSource protocol and shared source helpers."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Protocol

from wifi_contracts import NormalizedCsiFrame, SourceHealth, SourceManifest


class FrameSource(Protocol):
    """Unified input boundary for mock, replay, and live serial sources."""

    async def open(self) -> SourceManifest: ...

    def frames(self) -> AsyncIterator[NormalizedCsiFrame]: ...

    async def pause(self) -> None: ...

    async def resume(self) -> None: ...

    async def close(self) -> None: ...

    async def health(self) -> SourceHealth: ...
