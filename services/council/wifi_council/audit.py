"""Append-only council audit log and in-memory cycle store."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from wifi_contracts import CouncilCycleDetail, CouncilResult, CouncilUsageSummary


class CouncilAuditLog:
    """Append-only JSONL audit trail; entries are never modified or removed."""

    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def write(self, event: dict[str, Any]) -> None:
        entry = {
            "schema_version": "council-audit.v1",
            "emitted_at": datetime.now(UTC).isoformat(),
            **event,
        }
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(entry, sort_keys=True, ensure_ascii=False) + "\n")


class CouncilStore:
    """Keeps committed cycles (newest by sequence wins) for the API."""

    def __init__(self, audit: CouncilAuditLog | None = None) -> None:
        self.audit = audit
        self._cycles: dict[str, CouncilCycleDetail] = {}
        self._order: list[str] = []
        self._current: CouncilCycleDetail | None = None
        self._current_sequence = -1

    def commit(self, detail: CouncilCycleDetail, sequence: int) -> bool:
        """Sequence guard: an older cycle can never overwrite a newer one."""
        if sequence < self._current_sequence:
            return False
        if detail.cycle_id in self._cycles:
            return False
        self._cycles[detail.cycle_id] = detail
        self._order.append(detail.cycle_id)
        self._current = detail
        self._current_sequence = sequence
        if self.audit is not None:
            self.audit.write(
                {
                    "event_type": "council.commit",
                    "cycle_id": detail.cycle_id,
                    "evidence_hash": detail.evidence_hash,
                    "status": detail.status,
                    "sequence": sequence,
                }
            )
        return True

    @property
    def current(self) -> CouncilCycleDetail | None:
        return self._current

    @property
    def current_result(self) -> CouncilResult | None:
        return self._current.result if self._current is not None else None

    def cycle_ids(self, limit: int = 50) -> list[str]:
        return list(reversed(self._order[-limit:]))

    def get(self, cycle_id: str) -> CouncilCycleDetail | None:
        return self._cycles.get(cycle_id)

    def usage_summary(self) -> CouncilUsageSummary:
        calls = [
            record
            for detail in self._cycles.values()
            for record in detail.calls
        ]
        latencies = sorted(record.latency_ms for record in calls)
        median = (
            latencies[len(latencies) // 2]
            if latencies
            else 0.0
        )
        by_role: dict[str, int] = {}
        by_status: dict[str, int] = {}
        input_tokens = 0
        output_tokens = 0
        attempts = 0
        for record in calls:
            by_role[record.role] = by_role.get(record.role, 0) + 1
            by_status[record.status] = by_status.get(record.status, 0) + 1
            attempts += record.attempts
            input_tokens += record.input_tokens
            output_tokens += record.output_tokens
        return CouncilUsageSummary(
            schema_version="council-usage.v1",
            cycles_completed=len(self._order),
            total_calls=len(calls),
            total_attempts=attempts,
            calls_by_role=by_role,
            calls_by_status=by_status,
            total_input_tokens=input_tokens,
            total_output_tokens=output_tokens,
            p50_latency_ms=float(median),
        )
