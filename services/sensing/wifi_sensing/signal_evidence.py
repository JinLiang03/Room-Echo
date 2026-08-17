"""Evidence sealing: trigger, compact packet builder, append-only audit log."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from wifi_contracts import (
    CalibrationSummary,
    EvidencePacket,
    EvidenceValue,
    FeatureWindow,
    QualitySummary,
    SignalTriplet,
    SourceManifest,
    TopologySummary,
    WindowSummary,
)

from .calibration import CalibrationProfile
from .signal_config import SignalConfig


def quality_flags_for(
    triplet: SignalTriplet,
    window: FeatureWindow,
) -> list[str]:
    """Window-level quality flags carried into the sealed EvidencePacket."""
    flags: list[str] = []
    if triplet.status == "degraded":
        flags.append("degraded")
    elif triplet.status == "insufficient_signal":
        flags.append("insufficient_signal")
    elif triplet.status == "uncalibrated":
        flags.append("calibration_mismatch")
    if window.quality is not None:
        flags.extend(window.quality.ood_flags or [])
    return flags


class EvidenceTrigger:
    """Seal when: first candidate, >=3 s cooldown with a stable 3-window state
    change, or a major quality transition."""

    def __init__(self, config: SignalConfig) -> None:
        self.config = config
        self._last_candidate: tuple[Any, ...] | None = None
        self._change_count = 0

    def reset(self) -> None:
        self._last_candidate = None
        self._change_count = 0

    def should_seal(
        self,
        current: SignalTriplet,
        previous: SignalTriplet | None,
        *,
        now_s: float,
        last_seal_s: float | None,
    ) -> bool:
        if previous is None:
            return True
        cooldown_ready = (
            last_seal_s is None
            or now_s - last_seal_s >= self.config.evidence_cooldown_s
        )
        candidate = (
            current.motion.state,
            current.occupancy_density.state,
            current.depth_zone.state,
            current.status,
        )
        if candidate != self._last_candidate:
            self._change_count += 1
            self._last_candidate = candidate
        else:
            self._change_count = 0
        major_transition = current.status != previous.status
        return cooldown_ready and (
            major_transition
            or self._change_count >= self.config.evidence_stable_change_windows
        )


class EvidenceBuilder:
    """Builds a sealed, compact EvidencePacket; arrays never enter it."""

    def __init__(
        self,
        profile: CalibrationProfile,
        manifest: SourceManifest,
    ) -> None:
        self.profile = profile
        self.manifest = manifest

    def build(
        self,
        triplet: SignalTriplet,
        window: FeatureWindow,
        *,
        sequence: int,
        cycle_id: str,
    ) -> EvidencePacket:
        # Compact summaries: drop amplitude arrays, keep scalar features.
        summary_links = {
            link_id: feature.model_copy(
                update={"amplitude_median": [], "amplitude_mad": []}
            )
            for link_id, feature in window.links.items()
        }
        packet_coverage = min(
            (link.packet_coverage for link in window.links.values()),
            default=0.0,
        )
        evidence_index = {
            "signals/motion/value": EvidenceValue(
                path="signals/motion/value",
                value=triplet.motion.value,
                unit="ratio",
                description="motion intensity proxy",
            ),
            "signals/motion/state": EvidenceValue(
                path="signals/motion/state",
                value=triplet.motion.state,
                description="motion state",
            ),
            "signals/occupancy/state": EvidenceValue(
                path="signals/occupancy/state",
                value=triplet.occupancy_density.state,
                description="occupancy density proxy state",
            ),
            "signals/depth/state": EvidenceValue(
                path="signals/depth/state",
                value=triplet.depth_zone.state,
                description="depth zone proxy state",
            ),
            "quality/packet_coverage": EvidenceValue(
                path="quality/packet_coverage",
                value=round(packet_coverage, 6),
                unit="ratio",
                description="min link packet coverage",
            ),
            "quality/paired_coverage": EvidenceValue(
                path="quality/paired_coverage",
                value=round(window.paired_packet_coverage, 6),
                unit="ratio",
                description="paired packet coverage",
            ),
            "sensor/sensor_confidence_cap": EvidenceValue(
                path="sensor/sensor_confidence_cap",
                value=triplet.sensor_confidence_cap,
                unit="ratio",
                description="sensor confidence cap",
            ),
        }
        return EvidencePacket.create(
            schema_version="wifi-evidence.v1",
            session_id=triplet.session_id,
            cycle_id=cycle_id,
            sequence=sequence,
            captured_at=triplet.ended_at,
            source_manifest=self.manifest,
            window_summary=WindowSummary(
                window_id=window.window_id,
                start_ns=window.start_ns,
                end_ns=window.end_ns,
                stride_ms=window.stride_ms,
                links=summary_links,
                paired_packet_coverage=window.paired_packet_coverage,
            ),
            topology=TopologySummary(
                topology_hash=self.profile.topology_hash,
                link_ids=list(window.links),
                degraded_links=[],
                depth_output_allowed=len(window.links) >= 2,
            ),
            calibration=CalibrationSummary(
                calibration_profile_id=self.profile.profile_id,
                profile_hash=self.profile.checksum,
                calibrated_at=self.profile.fitted_at,
                room_conditions=self.profile.environment,
            ),
            quality=QualitySummary(
                overall_status=triplet.status,
                packet_coverage=round(packet_coverage, 6),
                link_health={
                    link_id: "ok" for link_id in window.links
                },
                quality_flags=quality_flags_for(triplet, window),
            ),
            signals=triplet,
            evidence_index=evidence_index,
            raw_ref=f"raw://{triplet.session_id}/{window.window_id}",
        )


class EvidenceLog:
    """Append-only audit log for sealed evidence (never modified)."""

    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def write(self, packet: EvidencePacket) -> None:
        entry = {
            "schema_version": "evidence-audit.v1",
            "event_type": "evidence.sealed",
            "session_id": packet.session_id,
            "cycle_id": packet.cycle_id,
            "sequence": packet.sequence,
            "evidence_hash": packet.evidence_hash,
            "status": packet.signals.status,
            "emitted_at": datetime.now(UTC).isoformat(),
        }
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(entry, sort_keys=True) + "\n")
