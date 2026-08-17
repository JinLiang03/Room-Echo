"""RecordSession: drives a FrameSource into a raw replay bundle."""

from __future__ import annotations

import time
from pathlib import Path

from wifi_contracts import CONTRACTS_VERSION

from .base import FrameSource
from .pairing import FramePairer
from .raw_writer import RawBundleWriter
from .replay_bundle import ReplayManifest
from .wire_conversion import wire_bytes_from_normalized


class RecordSession:
    """Records a source's frames into an append-only raw bundle.

    Every wire-format frame is appended before pairing (raw is append-only).
    Pairing counters are reported as events, not written into raw.
    """

    def __init__(
        self,
        *,
        source: FrameSource,
        session_id: str,
        raw_root: Path,
        collector_version: str = "0.1.0",
        firmware_version: str = "wifi-spatial-council-fw/0.1.0",
        topology_hash: str = "sha256:" + "0" * 64,
        calibration_profile_id: str | None = None,
        privacy: str = "raw CSI is local-only; MACs are hashed; no identity",
    ) -> None:
        self.source = source
        self.session_id = session_id
        self.raw_root = Path(raw_root)
        self.collector_version = collector_version
        self.firmware_version = firmware_version
        self.topology_hash = topology_hash
        self.calibration_profile_id = calibration_profile_id
        self.privacy = privacy
        self._writer: RawBundleWriter | None = None

    async def run(
        self,
        *,
        duration_s: float | None = None,
        pairer: FramePairer | None = None,
    ) -> Path:
        manifest_src = await self.source.open()
        pairer = pairer or FramePairer(
            links=tuple(manifest_src.link_ids),
        )
        manifest = ReplayManifest(
            schema_version="replay-manifest.v1",
            recording_id=self.session_id,
            session_id=self.session_id,
            created_at=manifest_src.session_started_at,
            source_mode=manifest_src.source_mode,
            firmware_version=self.firmware_version,
            collector_version=self.collector_version,
            contracts_version=CONTRACTS_VERSION,
            features_version=None,
            estimator_version=None,
            board_hashes={
                link: "sha256:" + "0" * 64 for link in manifest_src.link_ids
            },
            topology_hash=self.topology_hash,
            calibration_profile_id=self.calibration_profile_id,
            channel=6,
            bandwidth_mhz=20,
            files=[],
            ground_truth_present=False,
            privacy=self.privacy,
            status="incomplete",
        )
        self._writer = RawBundleWriter(
            session_id=self.session_id,
            raw_root=self.raw_root,
            manifest=manifest,
        )
        self._writer.start()
        self._writer.append_event(
            "session.started",
            {"source_mode": manifest_src.source_mode},
        )

        started = time.monotonic()
        frame_count = 0
        try:
            async for frame in self.source.frames():
                self._writer.append_wire_frame(wire_bytes_from_normalized(frame))
                frame_count += 1
                await pairer.feed(frame)
                if duration_s is not None and time.monotonic() - started >= duration_s:
                    break
        except BaseException as exc:
            assert self._writer is not None
            self._writer.abort(reason=f"{type(exc).__name__}: {exc}")
            raise

        await pairer.drain()
        assert self._writer is not None
        self._writer.append_event(
            "session.stopped",
            {
                "frames_recorded": frame_count,
                "pairing": pairer.counters.as_dict(),
            },
        )
        return self._writer.finalize()
