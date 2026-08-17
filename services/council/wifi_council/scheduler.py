"""Council scheduler: one active cycle plus one latest pending slot.

New evidence only replaces the pending slot; an old cycle finishing late can
never overwrite a newer committed snapshot (acceptance test section 5).
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime

from wifi_contracts import EvidencePacket

from .audit import CouncilAuditLog, CouncilStore
from .config import CouncilConfig
from .orchestrator import CouncilOrchestrator


class CouncilScheduler:
    def __init__(
        self,
        orchestrator: CouncilOrchestrator,
        store: CouncilStore,
        config: CouncilConfig,
        *,
        audit: CouncilAuditLog | None = None,
    ) -> None:
        self.orchestrator = orchestrator
        self.store = store
        self.config = config
        self.audit = audit
        self._running: asyncio.Task[None] | None = None
        self._pending: tuple[int, EvidencePacket] | None = None
        self._last_sequence = -1

    @property
    def is_running(self) -> bool:
        return self._running is not None and not self._running.done()

    @property
    def pending_sequence(self) -> int | None:
        return self._pending[0] if self._pending is not None else None

    def submit(self, packet: EvidencePacket) -> None:
        if self.audit is not None:
            self.audit.write(
                {
                    "event_type": "council.submitted",
                    "cycle_id": packet.cycle_id,
                    "evidence_hash": packet.evidence_hash,
                    "sequence": packet.sequence,
                }
            )
        if self.is_running:
            if self._pending is None or packet.sequence >= self._pending[0]:
                self._pending = (packet.sequence, packet)
            return
        self._running = asyncio.create_task(self._cycle(packet))

    async def _cycle(self, packet: EvidencePacket) -> None:
        try:
            detail = await asyncio.wait_for(
                self.orchestrator.run_cycle(packet),
                timeout=self.config.cycle_deadline_s,
            )
        except TimeoutError:
            detail = await self.orchestrator.deadline_result(
                packet,
                elapsed_s=self.config.cycle_deadline_s,
            )
        committed = self.store.commit(detail, packet.sequence)
        if committed:
            self._last_sequence = packet.sequence
            if self.audit is not None:
                self.audit.write(
                    {
                        "event_type": "council.result",
                        "cycle_id": detail.cycle_id,
                        "evidence_hash": detail.evidence_hash,
                        "status": detail.status,
                        "display_confidence": (
                            detail.result.display_confidence
                            if detail.result is not None
                            else 0.0
                        ),
                    }
                )
        next_packet = self._pending[1] if self._pending is not None else None
        next_sequence = self._pending[0] if self._pending is not None else None
        self._pending = None
        if next_packet is not None and next_sequence is not None:
            if next_sequence >= self._last_sequence:
                self._running = asyncio.create_task(self._cycle(next_packet))
                return
            self._running = None
            return
        self._running = None

    async def wait_idle(self, timeout_s: float = 30.0) -> bool:
        """Test helper: wait until no cycle is running and no slot is pending."""
        deadline = datetime.now(UTC).timestamp() + timeout_s
        while self.is_running or self.pending_sequence is not None:
            if datetime.now(UTC).timestamp() > deadline:
                return False
            await asyncio.sleep(0.01)
        return True
