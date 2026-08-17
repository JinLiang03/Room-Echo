"""Realtime stream: replay/mock/live -> features -> signals -> evidence -> council.

One session at a time, identified by a unique ``session_id`` per start.
Events carry a monotonic sequence and are retained in a bounded ring buffer
so a reconnecting client can resume from ``last_sequence``; a full snapshot
is always sent first (DATA_CONTRACTS §9). The council scheduler runs
independently, so the signal stream never waits for an LLM call.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import math
import queue
import random
import re
import statistics
import uuid
from collections import deque
from datetime import UTC, datetime
from pathlib import Path
from time import perf_counter
from typing import Any, Literal

from fastapi import WebSocket
from wifi_collector.mock_source import MockFrameSource
from wifi_collector.raw_writer import RawBundleWriter
from wifi_collector.replay_bundle import BundleVerifier, ReplayManifest
from wifi_collector.replay_source import ReplayFrameSource
from wifi_collector.serial_live import SerialLiveFrameSource
from wifi_collector.wire_conversion import wire_bytes_from_normalized
from wifi_contracts import (
    CONTRACTS_VERSION,
    CouncilResult,
    EvidencePacket,
    SignalTriplet,
    SourceManifest,
)
from wifi_council.config import CouncilConfig
from wifi_council.runtime import CouncilRuntime, build_provider
from wifi_sensing.calibration import (
    CalibrationProfile,
    demo_profile,
    profile_match_score,
)
from wifi_sensing.config import FeatureConfig
from wifi_sensing.pipeline import FeaturePipeline
from wifi_sensing.signal_config import SignalConfig
from wifi_sensing.signal_evidence import EvidenceBuilder, EvidenceTrigger, quality_flags_for
from wifi_sensing.signal_triplet import SignalEstimator

BUFFER_LIMIT = 400
SNAPSHOT_STATE_EVENT_LIMIT = 180
MODE = Literal["replay", "mock", "live"]
PROJECT_ROOT = Path(__file__).resolve().parents[3]
STREAM_LOG_DIR = PROJECT_ROOT / "data" / "derived" / "stream"
STORED_PROFILE = PROJECT_ROOT / "data" / "calibration" / "demo_room_v1" / "profile.json"
RAW_RECORDING_DIR = PROJECT_ROOT / "data" / "raw"
RAW_RECORD_QUEUE_LIMIT = 10_000
ZERO_HASH = "sha256:" + "0" * 64

DEMO_PHASES: list[tuple[str, float, float]] = [
    ("idle", 0.00, 0.16),
    ("far_entry", 0.16, 0.33),
    ("approach", 0.33, 0.54),
    ("occupancy_change", 0.54, 0.70),
    ("ambiguous_interference", 0.70, 0.88),
    ("recovery", 0.88, 1.01),
]


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


class CalibrationUnavailableError(ValueError):
    """Live sensing cannot start without a matching, non-simulated profile."""


def _load_profile(
    topology_hash: str,
    *,
    mode: MODE = "replay",
    profile_path: Path | None = None,
    channel: int = 6,
    bandwidth_mhz: int = 20,
    firmware_version: str = "wifi-spatial-council-fw/0.1.0",
) -> CalibrationProfile:
    """Load a profile, enforcing a strict trust boundary for Live mode.

    Replay and deterministic Mock remain allowed to use a generated demo
    profile. Live never falls back: its profile must be integrity-valid,
    active, recorded, non-simulated, fitted, and match the declared hardware
    topology/configuration. This prevents demo constants from becoming
    apparently confident physical output.
    """
    path = Path(profile_path) if profile_path is not None else STORED_PROFILE
    profile: CalibrationProfile | None = None
    load_error: str | None = None
    if path.is_file():
        try:
            profile = CalibrationProfile.model_validate_json(path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            load_error = f"profile is unreadable or invalid ({type(exc).__name__})"
    else:
        load_error = "profile file is missing"

    if mode != "live":
        if (
            profile is not None
            and profile.verify_integrity()
            and profile.state == "active"
            and profile.topology_hash == topology_hash
        ):
            return profile
        return demo_profile(FeatureConfig(), topology_hash)

    reasons: list[str] = []
    if topology_hash == ZERO_HASH:
        reasons.append("topology hash is an all-zero placeholder")
    if load_error is not None:
        reasons.append(load_error)
    if profile is not None:
        if not profile.verify_integrity():
            reasons.append("profile checksum failed")
        if profile.state != "active":
            reasons.append(f"profile state is {profile.state!r}, not 'active'")
        if profile.source != "recorded":
            reasons.append("profile source is not recorded")
        if profile.simulated:
            reasons.append("profile is marked simulated")
        if profile.fit_parameters is None:
            reasons.append("profile has no fitted signal parameters")
        if profile.metrics is None:
            reasons.append("profile has no held-out calibration metrics")
        elif profile.metrics.simulated:
            reasons.append("profile metrics are marked simulated")
        fitted_at = profile.fitted_at
        if fitted_at.tzinfo is None:
            fitted_at = fitted_at.replace(tzinfo=UTC)
        profile_age_days = (datetime.now(UTC) - fitted_at).total_seconds() / 86400
        if profile_age_days > profile.expiry.max_age_days:
            reasons.append("profile has expired by age")
        for link_id in ("rx-a", "rx-b"):
            board_hash = profile.board_hashes.get(link_id, "")
            if not re.fullmatch(r"sha256:[0-9a-f]{64}", board_hash) or board_hash == ZERO_HASH:
                reasons.append(f"profile board hash missing for {link_id}")
        _match_score, mismatches = profile_match_score(
            profile,
            topology_hash=topology_hash,
            channel=channel,
            bandwidth_mhz=bandwidth_mhz,
            firmware_version=firmware_version,
            feature_version=FeatureConfig().feature_version,
        )
        reasons.extend(f"profile mismatch: {field}" for field in mismatches)
    if reasons or profile is None:
        detail = "; ".join(dict.fromkeys(reasons)) or "profile unavailable"
        raise CalibrationUnavailableError(f"live calibration unavailable: {detail}")
    return profile


def demo_phase(position_s: float) -> str | None:
    """Phase label for the two-minute scripted demo, else None."""
    for name, start, end in DEMO_PHASES:
        if start <= position_s / 120.0 < end:
            return name
    return None


class _TimeoutProvider:
    """Fault-injected provider: every call exceeds the agent deadline."""

    name = "timeout"
    model = "mock"

    async def _wait(self) -> None:
        await asyncio.sleep(30)
        raise TimeoutError("fault-injected timeout")

    async def propose(self, *args: Any, **kwargs: Any) -> Any:
        await self._wait()

    async def challenge(self, *args: Any, **kwargs: Any) -> Any:
        await self._wait()

    async def respond(self, *args: Any, **kwargs: Any) -> Any:
        await self._wait()

    async def synthesize(self, *args: Any, **kwargs: Any) -> Any:
        await self._wait()

    def health(self) -> Any:
        from wifi_contracts import ProviderHealth

        return ProviderHealth(
            schema_version="provider-health.v1",
            provider="mock",
            status="degraded",
            model="mock",
            detail="fault-injected LLM timeout",
            checked_at=datetime.now(UTC),
        )


class StreamSession:
    """Runs one replay/mock/live source through sensing + council."""

    def __init__(
        self,
        *,
        mode: MODE = "replay",
        bundle_root: Path | None = None,
        scenario: str | None = None,
        rx_ports: dict[str, str] | None = None,
        rate: float = 1.0,
        paced: bool = True,
        recompute: bool = False,
        demo_scenario: bool = False,
        event_log_dir: Path = STREAM_LOG_DIR,
        raw_recording_dir: Path = RAW_RECORDING_DIR,
        calibration_profile_path: Path | None = None,
        live_topology_hash: str | None = None,
        council_config: CouncilConfig | None = None,
        council_runtime: CouncilRuntime | None = None,
    ) -> None:
        self.mode = mode
        self.bundle_root = Path(bundle_root) if bundle_root else None
        self.scenario = scenario
        self.rx_ports = dict(rx_ports or {})
        self._source_id = (
            self.bundle_root.name if self.bundle_root is not None else scenario or "live"
        )
        self.rate = rate
        self.paced = paced
        self.recompute = recompute
        self.demo_scenario = demo_scenario
        self.raw_recording_dir = Path(raw_recording_dir)
        self.calibration_profile_path = (
            Path(calibration_profile_path)
            if calibration_profile_path is not None
            else STORED_PROFILE
        )
        self.live_topology_hash = live_topology_hash
        self.session_id = f"{mode}-{self._source_id}-{uuid.uuid4().hex[:8]}"
        self.feature_config = FeatureConfig()
        self.signal_config = SignalConfig()
        self.council_config = council_config or CouncilConfig()
        self._source: Any = None
        self._task: asyncio.Task[None] | None = None
        self._frame_count = 0
        self._window_count = 0
        self._seal_count = 0
        self._position_s = 0.0
        self._recording = False
        self._recording_requested = False
        self._recording_frames = 0
        self._recording_bundle_id: str | None = None
        self._raw_writer: RawBundleWriter | None = None
        self._record_queue: queue.Queue[bytes | None] | None = None
        self._record_worker_task: asyncio.Task[None] | None = None
        self._record_worker_error: BaseException | None = None
        self._finished = False
        self._state: Literal[
            "idle", "starting", "running", "paused", "finished", "stopped", "error"
        ] = "idle"
        self._error: str | None = None
        self._manifest: Any = None
        self._source_manifest: SourceManifest | None = None
        self._profile: CalibrationProfile | None = None
        self._runtime: CouncilRuntime | None = None
        self._last_triplet: SignalTriplet | None = None
        self._last_result: CouncilResult | None = None
        self._last_cycle_ids: set[str] = set()
        self._cycle_timeline_revision: dict[str, int] = {}
        self._seen: dict[str, int] = {}
        self._hub: StreamHub | None = None
        self._spare_tasks: set[asyncio.Task[None]] = set()
        self._faults: dict[str, dict[str, Any]] = {}
        self._event_log_path: Path | None = None
        self._event_log_handle: Any | None = None
        self._window_latencies: deque[float] = deque(maxlen=1000)
        self._emit_times: deque[float] = deque(maxlen=400)
        self._snapshot_state_events: deque[dict[str, Any]] = deque(
            maxlen=SNAPSHOT_STATE_EVENT_LIMIT
        )
        self._latest_source_health: dict[str, Any] | None = None
        self._event_count = 0
        self._started_at: datetime | None = None
        self._profile_mismatch_hash: str | None = None
        self._fault_rng = random.Random(0xC011EC1)
        self._timeline_revision = 0
        self._step_remaining_to_process = 0
        self._step_complete: asyncio.Event | None = None
        self._council_runtime = council_runtime
        if event_log_dir is not None:
            self._event_log_path = Path(event_log_dir) / f"{self.session_id}.events.jsonl"
            self._event_log_path.parent.mkdir(parents=True, exist_ok=True)

    def _spawn(self, coro: Any) -> None:
        task = asyncio.create_task(coro)
        self._spare_tasks.add(task)
        task.add_done_callback(self._spare_tasks.discard)

    # ---- controls -------------------------------------------------------

    def attach(self, hub: StreamHub) -> None:
        self._hub = hub
        hub.on_publish = self._log_event

    def set_rate(self, rate: float) -> None:
        if not 0.25 <= rate <= 4.0:
            raise ValueError("rate must be within [0.25, 4.0]")
        self.rate = rate
        if self._source is not None and hasattr(self._source, "rate"):
            self._source.rate = rate
        self._emit_status()

    def pause(self) -> None:
        if self._source is not None:
            self._spawn(self._pause_and_report())
        else:
            self._emit_status()

    def resume(self) -> None:
        self._cancel_step_wait()
        if self._source is not None:
            self._spawn(self._resume_and_report())
        else:
            self._emit_status()

    async def _pause_and_report(self) -> None:
        if self._source is not None:
            await self._source.pause()
        if self._state in {"starting", "running", "paused"}:
            self._state = "paused"
        self._emit_status()

    async def _resume_and_report(self) -> None:
        if self._source is not None:
            await self._source.resume()
        if self._state in {"starting", "running", "paused"}:
            self._state = "running"
        self._emit_status()

    def seek(self, seconds: float) -> None:
        if not math.isfinite(seconds) or not 0.0 <= seconds <= 86_400.0:
            raise ValueError("seek seconds must be finite and within [0, 86400]")
        self._cancel_step_wait()
        if self._recording:
            # A rewind would make one raw bundle non-monotonic. Require an
            # explicit stop-record action so finalization remains auditable.
            self._emit(
                "alert",
                {
                    "level": "warn",
                    "message": "stop raw recording before seeking replay",
                },
            )
            self._emit_status()
            return
        if self._source is not None and hasattr(self._source, "seek"):
            self._source.seek(seconds)
            self._position_s = max(0.0, seconds)
            revision = int(getattr(self._source, "control_revision", self._timeline_revision + 1))
            self._reset_timeline_view(revision)
        self._emit_status()

    def step(self, frames: int) -> None:
        if not 1 <= frames <= 10_000:
            raise ValueError("step frames must be within [1, 10000]")
        if self._source is not None and hasattr(self._source, "step"):
            self._step_remaining_to_process = frames
            self._step_complete = asyncio.Event()
            self._source.step(frames)
            if getattr(self._source, "is_paused", False):
                self._state = "paused"
        self._emit_status()

    async def step_and_wait(self, frames: int, *, timeout_s: float = 5.0) -> None:
        """Apply a paused step and wait until those raw frames are processed."""
        self.step(frames)
        complete = self._step_complete
        if complete is None:
            return
        try:
            await asyncio.wait_for(complete.wait(), timeout=timeout_s)
        except TimeoutError:
            self._emit(
                "alert",
                {
                    "level": "warn",
                    "message": "replay step did not complete before timeout",
                },
            )
        self._emit_status()

    def _mark_step_processed(self) -> None:
        if self._step_remaining_to_process <= 0:
            return
        self._step_remaining_to_process -= 1
        if self._step_remaining_to_process == 0 and self._step_complete is not None:
            self._step_complete.set()

    def _cancel_step_wait(self) -> None:
        self._step_remaining_to_process = 0
        if self._step_complete is not None:
            self._step_complete.set()
        self._step_complete = None

    def _reset_timeline_view(self, revision: int) -> None:
        """Clear derived presentation state when replay moves discontinuously."""
        self._timeline_revision = max(0, revision)
        self._frame_count = 0
        self._window_count = 0
        self._seal_count = 0
        self._last_triplet = None
        self._last_result = None
        self._snapshot_state_events.clear()
        if self._hub is not None:
            self._hub.clear_history()

    def _emit_status(self) -> None:
        self._emit("session.status", self.status())

    async def toggle_recording(self) -> None:
        try:
            if self._recording:
                self._recording_requested = False
                await self._finalize_recording(complete=True)
            elif self._state in {"finished", "stopped", "error"}:
                self._emit(
                    "alert",
                    {
                        "level": "warn",
                        "message": "raw recording requires an active stream",
                    },
                )
            elif self._source_manifest is None or self._profile is None:
                self._recording_requested = True
            else:
                self._recording_requested = True
                self._start_recording()
        except Exception as exc:
            self._fail_recording_control(exc)
        self._emit_status()

    def _fail_recording_control(self, exc: Exception) -> None:
        self._error = f"raw recording failed; stream stopped ({type(exc).__name__})"
        self._state = "error"
        writer = self._raw_writer
        if writer is not None and self._record_worker_task is None:
            with contextlib.suppress(Exception):
                writer.abort(reason=f"recording control failed: {type(exc).__name__}")
        self._recording = False
        self._recording_requested = False
        self._raw_writer = None
        self._emit("alert", {"level": "error", "message": self._error})
        if self._task is not None and not self._task.done():
            self._task.cancel()

    def _start_recording(self) -> None:
        if self._recording or not self._recording_requested:
            return
        manifest_src = self._source_manifest
        profile = self._profile
        if manifest_src is None or profile is None:
            return
        recording_id = f"{self.session_id}-capture-{uuid.uuid4().hex[:8]}"
        firmware_version = (
            manifest_src.firmware_versions.get("firmware")
            or manifest_src.firmware_versions.get("csi_rx")
            or next(iter(manifest_src.firmware_versions.values()), "unknown")
        )
        manifest = ReplayManifest(
            schema_version="replay-manifest.v1",
            recording_id=recording_id,
            session_id=self.session_id,
            created_at=datetime.now(UTC),
            source_mode=manifest_src.source_mode,
            firmware_version=firmware_version,
            collector_version="0.1.0",
            contracts_version=CONTRACTS_VERSION,
            features_version=None,
            estimator_version=None,
            board_hashes={
                link_id: profile.board_hashes.get(link_id, "unknown")
                for link_id in manifest_src.link_ids
            },
            topology_hash=manifest_src.topology_hash,
            calibration_profile_id=profile.profile_id,
            channel=profile.channel,
            bandwidth_mhz=profile.bandwidth_mhz,
            files=[],
            ground_truth_present=False,
            privacy=(
                "raw CSI is local-only sensitive sensor data; MAC identifiers "
                "are hashed; no identity inference"
            ),
            status="incomplete",
        )
        writer = RawBundleWriter(
            session_id=recording_id,
            raw_root=self.raw_recording_dir,
            manifest=manifest,
        )
        try:
            writer.start()
            self._raw_writer = writer
            writer.append_event(
                "recording.started",
                {
                    "source_mode": manifest_src.source_mode,
                    "topology_hash": manifest_src.topology_hash,
                    "calibration_profile_id": profile.profile_id,
                },
            )
            self._recording = True
            self._recording_frames = 0
            self._recording_bundle_id = recording_id
            self._record_worker_error = None
            self._record_queue = queue.Queue(maxsize=RAW_RECORD_QUEUE_LIMIT)
            self._record_worker_task = asyncio.create_task(
                asyncio.to_thread(self._recording_worker)
            )
        except Exception as exc:
            with contextlib.suppress(Exception):
                writer.abort(reason=f"recording start failed: {type(exc).__name__}")
            self._raw_writer = None
            self._record_queue = None
            self._record_worker_task = None
            self._record_worker_error = None
            self._recording = False
            self._recording_requested = False
            raise

    def _recording_worker(self) -> None:
        """Drain raw bytes on a worker thread; never block the signal loop."""
        writer = self._raw_writer
        outbox = self._record_queue
        if writer is None or outbox is None:
            return
        failed = False
        while True:
            item = outbox.get()
            try:
                if item is None:
                    return
                if failed:
                    continue
                try:
                    writer.append_wire_frame(item)
                    self._recording_frames += 1
                except BaseException as exc:
                    self._record_worker_error = exc
                    failed = True
            finally:
                outbox.task_done()

    def _append_recording_frame(self, frame: Any) -> None:
        outbox = self._record_queue
        if outbox is None:
            return
        if self._record_worker_error is not None:
            raise RuntimeError("raw recording worker failed; stream stopped") from (
                self._record_worker_error
            )
        try:
            outbox.put_nowait(wire_bytes_from_normalized(frame))
        except queue.Full as exc:
            raise RuntimeError("raw recording queue full; stream stopped") from exc

    async def _finalize_recording(self, *, complete: bool) -> None:
        writer = self._raw_writer
        if writer is None:
            self._recording = False
            return
        outbox = self._record_queue
        worker = self._record_worker_task
        try:
            if outbox is not None and worker is not None:
                await asyncio.to_thread(outbox.put, None)
                await worker
            worker_error = self._record_worker_error
            writer.append_event(
                "recording.stopped" if complete else "recording.aborted",
                {"frames_recorded": self._recording_frames},
            )
            if complete and worker_error is None:
                await asyncio.to_thread(writer.finalize)
            else:
                reason = (
                    f"raw writer failed: {type(worker_error).__name__}"
                    if worker_error is not None
                    else "stream ended with an error"
                )
                await asyncio.to_thread(writer.abort, reason=reason)
            if worker_error is not None:
                raise RuntimeError("raw recording worker failed; bundle is incomplete") from (
                    worker_error
                )
        finally:
            self._raw_writer = None
            self._record_queue = None
            self._record_worker_task = None
            self._record_worker_error = None
            self._recording = False
            self._recording_requested = False

    # ---- faults ---------------------------------------------------------

    def activate_fault(self, name: str, params: dict[str, Any] | None = None) -> None:
        known = {
            "packet_loss",
            "single_rx",
            "tx_stale",
            "profile_mismatch",
            "llm_timeout",
            "invalid_json",
            "disk_error",
            "ws_disconnect",
        }
        if name not in known:
            raise ValueError(f"unknown fault: {name}")
        self._faults[name] = dict(params or {})
        if name == "tx_stale":
            self.pause()
        elif name == "profile_mismatch":
            self._profile_mismatch_hash = "sha256:" + "f" * 64
        elif name == "llm_timeout":
            self._activate_timeout_provider()
        elif name == "invalid_json":
            self._activate_bad_provider()
        elif name == "disk_error":
            self._emit(
                "alert",
                {"level": "error", "message": "disk write error (simulated fault)"},
            )
        self._emit_status()

    def deactivate_fault(self, name: str) -> None:
        self._faults.pop(name, None)
        if name == "tx_stale":
            self.resume()
        elif name == "profile_mismatch":
            self._profile_mismatch_hash = None
        elif name == "llm_timeout" or name == "invalid_json":
            self._restore_provider()
        self._emit_status()

    def faults_summary(self) -> dict[str, dict[str, Any]]:
        return dict(self._faults)

    def _activate_timeout_provider(self) -> None:
        if self._runtime is not None:
            self._runtime.orchestrator.config = self.council_config
            self._runtime.orchestrator.provider = _TimeoutProvider()

    def _apply_faults_to_runtime(self) -> None:
        """Apply faults that were activated before the runtime existed."""
        if self._runtime is None:
            return
        if "llm_timeout" in self._faults:
            self._activate_timeout_provider()
        if "invalid_json" in self._faults:
            self._activate_bad_provider()

    def _activate_bad_provider(self) -> None:
        if self._runtime is not None:
            from wifi_council.provider import MockAgentProvider

            self._runtime.orchestrator.provider = MockAgentProvider(
                self.council_config,
                misbehave="overreach",
            )

    def _restore_provider(self) -> None:
        if self._runtime is not None:
            self._runtime.orchestrator.provider = build_provider(
                self.council_config,
                demo_scenario=self.demo_scenario,
            )

    # ---- lifecycle ------------------------------------------------------

    def start(self) -> None:
        if self._task is None or self._task.done():
            self._finished = False
            self._error = None
            self._state = "starting"
            self._task = asyncio.create_task(self._run())
            self._emit_status()

    async def wait_finished(self) -> None:
        """Wait for this run without transferring cancellation to its task."""
        task = self._task
        if task is not None:
            await asyncio.shield(task)

    async def stop(self) -> None:
        self._cancel_step_wait()
        if self._source is not None:
            await self._source.close()
        if self._task is not None:
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task
        if self._recording:
            try:
                await self._finalize_recording(complete=True)
            except Exception as exc:
                self._fail_recording_control(exc)
                self._emit_status()
                return
        self._recording_requested = False
        self._state = "stopped"
        self._close_log()
        self._emit_status()

    @property
    def is_running(self) -> bool:
        return (
            self._task is not None
            and not self._task.done()
            and self._state in {"starting", "running", "paused"}
        )

    @property
    def latest_source_health(self) -> dict[str, Any] | None:
        return dict(self._latest_source_health) if self._latest_source_health is not None else None

    def status(self) -> dict[str, Any]:
        phase = demo_phase(self._position_s) if self._source_id == "demo_2min" else None
        paused = self._source is not None and getattr(self._source, "is_paused", False)
        state = (
            "paused" if paused and self._state in {"starting", "running", "paused"} else self._state
        )
        return {
            "schema_version": "stream-status.v1",
            "session_id": self.session_id,
            "state": state,
            "timeline_revision": self._timeline_revision,
            "mode": self.mode,
            "source_id": self._source_id,
            "bundle_id": (
                self._manifest.recording_id if self._manifest is not None else self._source_id
            ),
            "running": self.is_running,
            "finished": self._finished,
            "paused": paused,
            "rate": self.rate,
            "position_s": round(self._position_s, 3),
            "demo_phase": phase,
            "frames": self._frame_count,
            "windows": self._window_count,
            "evidence_seals": self._seal_count,
            "recording": self._recording,
            "recording_bundle_id": self._recording_bundle_id,
            "recompute": self.recompute,
            "ground_truth_present": bool(getattr(self._manifest, "ground_truth_present", False)),
            "faults": self.faults_summary(),
            "error": self._error,
            "updated_at": _now_iso(),
        }

    def metrics(self) -> dict[str, Any]:
        latencies = list(self._window_latencies)
        quantiles = {}
        if latencies:
            sorted_values = sorted(latencies)
            quantiles = {
                "p50_ms": round(statistics.median(sorted_values), 3),
                "p95_ms": round(
                    sorted_values[min(len(sorted_values) - 1, int(len(sorted_values) * 0.95))],
                    3,
                ),
                "p99_ms": round(
                    sorted_values[min(len(sorted_values) - 1, int(len(sorted_values) * 0.99))],
                    3,
                ),
                "count": len(sorted_values),
            }
        events = list(self._emit_times)
        event_rate = 0.0
        if len(events) >= 2:
            span = (events[-1] - events[0]) / 1000
            if span > 0:
                event_rate = round(len(events) / span, 2)
        return {
            "session_id": self.session_id,
            "window_latency_ms": quantiles,
            "window_latency_definition": (
                "last raw frame processing start to event-hub publish; "
                "network delivery excluded"
            ),
            "event_rate_hz": event_rate,
            "events": self._event_count,
            "queue_depth": len(self._hub._buffer) if self._hub else 0,
            "frames": self._frame_count,
            "windows": self._window_count,
            "errors": [self._error] if self._error else [],
        }

    # ---- events & log ---------------------------------------------------

    def _log_event(self, event: dict[str, Any]) -> None:
        self._event_count += 1
        self._emit_times.append(float(_parse_ms(event["emitted_at"])))
        event_type = event.get("event_type")
        if event_type == "source.health":
            self._latest_source_health = dict(event.get("payload", {}))
        if event_type not in {
            "signal.frame",
            "quality.update",
            "source.health",
            "heartbeat",
        }:
            self._snapshot_state_events.append(event)
        if self._event_log_handle is not None:
            self._event_log_handle.write(
                json.dumps(event, sort_keys=True, ensure_ascii=False) + "\n"
            )

    def _open_log(self) -> None:
        if self._event_log_path is not None:
            self._event_log_handle = self._event_log_path.open("a", encoding="utf-8")

    def _close_log(self) -> None:
        if self._event_log_handle is not None:
            self._event_log_handle.close()
            self._event_log_handle = None

    def _emit(self, event_type: str, payload: dict[str, Any]) -> None:
        if self._hub is None:
            return
        self._hub.publish(self.session_id, event_type, payload)

    # ---- source & pipeline ----------------------------------------------

    async def _open_source(self) -> Any:
        if self.mode == "replay":
            if self.bundle_root is None:
                raise ValueError("replay mode requires bundle_root")
            verifier = BundleVerifier(self.bundle_root)
            result = await asyncio.to_thread(verifier.verify)
            if not result.ok or result.manifest is None:
                raise ValueError("; ".join(result.errors))
            self._manifest = result.manifest
            return ReplayFrameSource(
                self.bundle_root,
                rate=self.rate,
                recompute=self.recompute,
                real_time=self.paced,
            )
        if self.mode == "mock":
            duration = 120.0 if self.scenario == "demo_2min" else 90.0
            return MockFrameSource(
                scenario=self.scenario or "walk_through",
                seed=0xC5F15EED,
                rate_hz=100,
                duration_s=duration,
                session_id=self.session_id,
                real_time=self.paced,
            )
        if self.mode == "live":
            if not self.rx_ports.get("rx-a") or not self.rx_ports.get("rx-b"):
                raise ValueError(
                    "live mode requires explicit RX_PORTS (e.g. RX_PORTS=rx-a=/dev/ttyUSB0,rx-b=/dev/ttyUSB1)"
                )
            return SerialLiveFrameSource(
                session_id=self.session_id,
                rx_a_port=self.rx_ports["rx-a"],
                rx_b_port=self.rx_ports["rx-b"],
            )
        raise ValueError(f"unknown mode: {self.mode}")

    async def _source_health_payload(
        self,
        source: Any,
        manifest: SourceManifest,
        profile: CalibrationProfile,
    ) -> dict[str, Any]:
        health = await source.health()
        payload: dict[str, Any] = dict(health.model_dump(mode="json"))
        payload.update(
            {
                # A replay bundle has its own historical session id; realtime
                # envelopes and payloads consistently use this run's id.
                "session_id": self.session_id,
                "source_mode": manifest.source_mode,
                "link_ids": manifest.link_ids,
                "topology_hash": manifest.topology_hash,
                "calibration_profile_id": profile.profile_id,
                "calibration_simulated": profile.simulated,
                "calibration_source": profile.source,
                "calibration_state": profile.state,
                "channel": profile.channel,
                "bandwidth_mhz": profile.bandwidth_mhz,
                "recompute": self.recompute,
            }
        )
        return payload

    async def _source_health_bridge(
        self,
        source: Any,
        manifest: SourceManifest,
        profile: CalibrationProfile,
    ) -> None:
        """Refresh source link/counter health without blocking signal flow."""
        previous: str | None = None
        while True:
            try:
                payload = await self._source_health_payload(
                    source,
                    manifest,
                    profile,
                )
                material = dict(payload)
                material.pop("updated_at", None)
                signature = json.dumps(material, sort_keys=True)
                if signature != previous:
                    self._emit("source.health", payload)
                    previous = signature
            except Exception as exc:
                self._emit(
                    "source.health",
                    {
                        "schema_version": "source-health.v1",
                        "session_id": self.session_id,
                        "source_mode": manifest.source_mode,
                        "status": "error",
                        "active_links": [],
                        "degraded_links": list(manifest.link_ids),
                        "dropped_links": list(manifest.link_ids),
                        "counters": {},
                        "epoch": 0,
                        "updated_at": _now_iso(),
                        "link_ids": manifest.link_ids,
                        "topology_hash": manifest.topology_hash,
                        "calibration_profile_id": profile.profile_id,
                        "calibration_simulated": profile.simulated,
                        "calibration_source": profile.source,
                        "calibration_state": profile.state,
                        "channel": profile.channel,
                        "bandwidth_mhz": profile.bandwidth_mhz,
                        "recompute": self.recompute,
                        "detail": f"health query failed ({type(exc).__name__})",
                    },
                )
            await asyncio.sleep(1.0)

    def validate_live_configuration(self) -> CalibrationProfile:
        """Validate Live prerequisites without opening serial devices."""
        if self.mode != "live":
            raise ValueError("live configuration validation requires live mode")
        if not self.rx_ports.get("rx-a") or not self.rx_ports.get("rx-b"):
            raise CalibrationUnavailableError(
                "live source unavailable: explicit rx-a and rx-b ports are required"
            )
        topology_hash = self.live_topology_hash or ""
        if not re.fullmatch(r"sha256:[0-9a-f]{64}", topology_hash):
            raise CalibrationUnavailableError(
                "live topology unavailable: set LIVE_TOPOLOGY_HASH to a sha256 hash"
            )
        return _load_profile(
            topology_hash,
            mode="live",
            profile_path=self.calibration_profile_path,
            channel=self.feature_config.expected_channel,
            bandwidth_mhz=self.feature_config.expected_bandwidth_mhz,
        )

    def _profile_for(self, manifest: SourceManifest) -> CalibrationProfile:
        if self._profile_mismatch_hash is not None:
            if self.mode == "live":
                raise CalibrationUnavailableError(
                    "live calibration unavailable: injected topology mismatch"
                )
            return demo_profile(self.feature_config, self._profile_mismatch_hash)
        firmware_version = (
            manifest.firmware_versions.get("firmware")
            or manifest.firmware_versions.get("csi_rx")
            or "wifi-spatial-council-fw/0.1.0"
        )
        return _load_profile(
            manifest.topology_hash,
            mode=self.mode,
            profile_path=self.calibration_profile_path,
            channel=self.feature_config.expected_channel,
            bandwidth_mhz=self.feature_config.expected_bandwidth_mhz,
            firmware_version=firmware_version,
        )

    def _should_drop_frame(self, link_id: str, rng: Any) -> bool:
        packet_loss = self._faults.get("packet_loss", {}).get("ratio", 0.0)
        if rng.random() < float(packet_loss or 0.0):
            return True
        return "single_rx" in self._faults and link_id != self._faults["single_rx"].get(
            "keep_link", "rx-a"
        )

    async def _run(self) -> None:
        self._started_at = datetime.now(UTC)
        self._open_log()
        bridge: asyncio.Task[None] | None = None
        health_bridge: asyncio.Task[None] | None = None
        try:
            source = await self._open_source()
            self._source = source
            manifest = await source.open()
            manifest_update: dict[str, Any] = {"session_id": self.session_id}
            if self.mode == "live":
                self.validate_live_configuration()
                manifest_update["topology_hash"] = self.live_topology_hash
            manifest = SourceManifest.model_validate(
                {
                    **manifest.model_dump(mode="python"),
                    **manifest_update,
                }
            )
            self._source_manifest = manifest
            profile = self._profile_for(manifest)
            self._profile = profile
            self._state = "running"
            if self._recording_requested:
                self._start_recording()
            self._emit_status()
            pipeline = FeaturePipeline(self.feature_config, profile)
            estimator = SignalEstimator(self.signal_config, profile)
            trigger = EvidenceTrigger(self.signal_config)
            builder = EvidenceBuilder(profile, manifest)
            runtime = self._council_runtime or CouncilRuntime(
                self.council_config,
                provider=build_provider(
                    self.council_config,
                    demo_scenario=self.demo_scenario,
                ),
            )
            self._runtime = runtime
            self._apply_faults_to_runtime()
            bridge = asyncio.create_task(self._council_bridge())
            self._emit(
                "source.health",
                await self._source_health_payload(source, manifest, profile),
            )
            health_bridge = asyncio.create_task(
                self._source_health_bridge(source, manifest, profile)
            )
            previous: SignalTriplet | None = None
            last_seal_s: float | None = None
            sequence = 0
            cycle = 0
            now_s = 0.0
            last_window = None
            frame_revision = int(getattr(source, "frame_revision", 0))
            async for frame in source.frames():
                next_revision = int(getattr(source, "frame_revision", 0))
                if next_revision != frame_revision:
                    pipeline.reset()
                    estimator.reset()
                    trigger.reset()
                    previous = None
                    last_seal_s = None
                    last_window = None
                    now_s = float(getattr(source, "position_s", self._position_s))
                    self._position_s = now_s
                    frame_revision = next_revision
                    if self._timeline_revision != next_revision:
                        self._reset_timeline_view(next_revision)
                    self._emit_status()
                    unavailable = estimator.estimate_stale(
                        session_id=manifest.session_id,
                        source_mode=manifest.source_mode,
                        window_id=f"seek-{frame_revision}",
                    )
                    self._last_triplet = unavailable
                    self._emit(
                        "signal.frame",
                        {"triplet": unavailable.model_dump(mode="json")},
                    )
                self._append_recording_frame(frame)
                self._frame_count += 1
                if self._should_drop_frame(frame.link_id, self._fault_rng):
                    self._mark_step_processed()
                    continue
                frame_processing_started = perf_counter()
                for window in pipeline.transform([frame], manifest):
                    self._window_count += 1
                    last_window = window
                    now_s = window.end_ns / 1_000_000_000
                    self._position_s = now_s
                    triplet = estimator.estimate(window)
                    self._last_triplet = triplet
                    self._emit(
                        "signal.frame",
                        {"triplet": triplet.model_dump(mode="json")},
                    )
                    self._window_latencies.append(
                        (perf_counter() - frame_processing_started) * 1000
                    )
                    cooldown_ready = (
                        last_seal_s is None
                        or now_s - last_seal_s >= self.signal_config.evidence_cooldown_s
                    )
                    periodic_demo = (
                        self._source_id == "demo_2min"
                        and cooldown_ready
                        and last_seal_s is not None
                        and now_s - last_seal_s >= 12.0
                    )
                    if (
                        trigger.should_seal(
                            triplet,
                            previous,
                            now_s=now_s,
                            last_seal_s=last_seal_s,
                        )
                        or periodic_demo
                    ):
                        cycle += 1
                        sequence += 1
                        packet = builder.build(
                            triplet,
                            window,
                            sequence=sequence,
                            cycle_id=f"cycle-{cycle:04d}",
                        )
                        packet = self._with_quality_flags(packet, triplet, window, now_s)
                        self._seal_count += 1
                        self._cycle_timeline_revision[packet.cycle_id] = self._timeline_revision
                        runtime.scheduler.submit(packet)
                        self._emit(
                            "cycle.started",
                            {
                                "cycle_id": packet.cycle_id,
                                "evidence_hash": packet.evidence_hash,
                                "sequence": sequence,
                            },
                        )
                        self._emit(
                            "quality.update",
                            self._quality_payload(triplet, window, now_s),
                        )
                        last_seal_s = now_s
                    previous = triplet
                    await asyncio.sleep(0)
                self._mark_step_processed()

            if previous is not None and last_window is not None:
                stale = estimator.estimate_stale(
                    session_id=manifest.session_id,
                    source_mode=manifest.source_mode,
                )
                if trigger.should_seal(
                    stale,
                    previous,
                    now_s=now_s + 100.0,
                    last_seal_s=last_seal_s,
                ):
                    cycle += 1
                    sequence += 1
                    packet = builder.build(
                        stale,
                        last_window,
                        sequence=sequence,
                        cycle_id=f"cycle-{cycle:04d}",
                    )
                    self._seal_count += 1
                    self._cycle_timeline_revision[packet.cycle_id] = self._timeline_revision
                    runtime.scheduler.submit(packet)
                    self._emit(
                        "cycle.started",
                        {
                            "cycle_id": packet.cycle_id,
                            "evidence_hash": packet.evidence_hash,
                            "sequence": sequence,
                        },
                    )
                    self._emit(
                        "quality.update",
                        {
                            "window_id": last_window.window_id,
                            "status": stale.status,
                            "packet_coverage": 0.0,
                            "paired_coverage": 0.0,
                            "link_health": {link_id: "stale" for link_id in last_window.links},
                            "quality_flags": ["stale"],
                        },
                    )

            await runtime.scheduler.wait_idle(timeout_s=30.0)
            self._drain_council(runtime)
            bridge.cancel()
            if self._recording:
                await self._finalize_recording(complete=True)
            self._finished = True
            self._state = "finished"
            self._cancel_step_wait()
            self._emit_status()
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            self._error = str(exc)[:500]
            self._state = "error"
            self._cancel_step_wait()
            if self._recording:
                with contextlib.suppress(Exception):
                    await self._finalize_recording(complete=False)
            self._emit("alert", {"level": "error", "message": self._error})
            self._emit_status()
        finally:
            for background in (bridge, health_bridge):
                if background is None:
                    continue
                if not background.done():
                    background.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await background
            if self._source is not None:
                with contextlib.suppress(Exception):
                    await self._source.close()
            self._close_log()

    def _quality_payload(
        self,
        triplet: SignalTriplet,
        window: Any,
        now_s: float,
    ) -> dict[str, Any]:
        flags = self._scenario_flags(triplet, window, now_s)
        return {
            "window_id": window.window_id,
            "status": triplet.status,
            "packet_coverage": round(
                min(
                    (link.packet_coverage for link in window.links.values()),
                    default=0.0,
                ),
                6,
            ),
            "paired_coverage": round(window.paired_packet_coverage, 6),
            "link_health": {link_id: "ok" for link_id in window.links},
            "quality_flags": flags,
        }

    def _scenario_flags(
        self,
        triplet: SignalTriplet,
        window: Any,
        now_s: float,
    ) -> list[str]:
        flags = quality_flags_for(triplet, window)
        if self._source_id == "demo_2min" and demo_phase(now_s) == "ambiguous_interference":
            flags.append("interference_high")
        if self.mode == "mock" and getattr(self._source, "scenario", None) is not None:
            scenario = self._source.scenario
            if getattr(scenario, "interference", False):
                flags.append("interference_high")
        return flags

    def _with_quality_flags(
        self,
        packet: EvidencePacket,
        triplet: SignalTriplet,
        window: Any,
        now_s: float,
    ) -> EvidencePacket:
        flags = self._scenario_flags(triplet, window, now_s)
        if not flags:
            return packet
        updated = packet.model_copy(
            update={"quality": packet.quality.model_copy(update={"quality_flags": flags})}
        )
        return EvidencePacket.create(**updated.model_dump())

    async def _council_bridge(self) -> None:
        runtime = self._runtime
        if runtime is None:
            return
        while True:
            self._drain_council(runtime)
            await asyncio.sleep(0.05)

    def _drain_council(self, runtime: CouncilRuntime) -> None:
        for cycle_id in runtime.store.cycle_ids(limit=100):
            detail = runtime.store.get(cycle_id)
            if detail is None:
                continue
            if self._cycle_timeline_revision.get(cycle_id) != self._timeline_revision:
                self._last_cycle_ids.add(cycle_id)
                self._seen[f"{cycle_id}:result"] = 1
                continue
            if cycle_id not in self._last_cycle_ids:
                self._last_cycle_ids.add(cycle_id)
                self._emit(
                    "agent.claim",
                    {
                        "cycle_id": cycle_id,
                        "claims": [claim.model_dump(mode="json") for claim in detail.claims],
                        "challenges": [
                            challenge.model_dump(mode="json") for challenge in detail.challenges
                        ],
                        "rejections": [
                            rejection.model_dump(mode="json") for rejection in detail.rejections
                        ],
                    },
                )
            if detail.result is not None:
                key = f"{cycle_id}:result"
                if self._seen.get(key, 0) == 0:
                    self._seen[key] = 1
                    self._last_result = detail.result
                    self._emit(
                        "synthesis.result",
                        {
                            "cycle_id": cycle_id,
                            "result": detail.result.model_dump(mode="json"),
                        },
                    )

    def snapshot(self) -> dict[str, Any]:
        events_by_sequence = {
            int(event["sequence"]): event
            for event in self._snapshot_state_events
            if event.get("session_id") == self.session_id
        }
        if self._hub is not None:
            events_by_sequence.update(
                {
                    int(event["sequence"]): event
                    for event in self._hub._buffer
                    if event.get("session_id") == self.session_id
                }
            )
        return {
            "event_type": "snapshot",
            "payload": {
                "status": self.status(),
                "latest_triplet": (
                    self._last_triplet.model_dump(mode="json")
                    if self._last_triplet is not None
                    else None
                ),
                "latest_result": (
                    self._last_result.model_dump(mode="json")
                    if self._last_result is not None
                    else None
                ),
                "latest_source_health": self._latest_source_health,
                "recent_events": [
                    events_by_sequence[sequence] for sequence in sorted(events_by_sequence)
                ],
            },
        }


class StreamHub:
    """Publishes stream events with monotonic sequences + ring buffer."""

    def __init__(self, buffer_limit: int = BUFFER_LIMIT) -> None:
        self._sequence = 0
        self._buffer: deque[dict[str, Any]] = deque(maxlen=buffer_limit)
        self._clients: set[WebSocket] = set()
        self._session: StreamSession | None = None
        self.on_publish: Any | None = None
        self._spare_tasks: set[asyncio.Task[None]] = set()

    def _spawn(self, coro: Any) -> None:
        task = asyncio.create_task(coro)
        self._spare_tasks.add(task)
        task.add_done_callback(self._spare_tasks.discard)

    def attach_session(self, session: StreamSession) -> None:
        if self._session is session:
            session.attach(self)
            return
        for task in list(self._spare_tasks):
            task.cancel()
        self._spare_tasks.clear()
        self._buffer.clear()
        self._sequence = 0
        self._session = session
        session.attach(self)

    def detach_session(self) -> None:
        self._session = None
        self.on_publish = None
        self._buffer.clear()
        self._sequence = 0

    def clear_history(self) -> None:
        """Drop replayable events without breaking session sequence monotonicity."""
        self._buffer.clear()

    @property
    def session(self) -> StreamSession | None:
        return self._session

    def publish(self, session_id: str, event_type: str, payload: dict[str, Any]) -> None:
        self._sequence += 1
        event: dict[str, Any] = {
            "schema_version": "ws-event.v1",
            "session_id": session_id,
            "sequence": self._sequence,
            "emitted_at": _now_iso(),
            "event_type": event_type,
            "payload": payload,
        }
        self._buffer.append(event)
        if self.on_publish is not None:
            self.on_publish(event)
        for client in list(self._clients):
            self._spawn(self._send(client, event))

    async def _send(self, client: WebSocket, event: dict[str, Any]) -> None:
        try:
            await client.send_text(json.dumps(event, ensure_ascii=False))
        except Exception:
            self._clients.discard(client)

    async def connect(
        self,
        websocket: WebSocket,
        *,
        last_sequence: int | None = None,
    ) -> None:
        await websocket.accept()
        self._clients.add(websocket)
        snapshot = self.snapshot(last_sequence)
        await websocket.send_text(json.dumps(snapshot, ensure_ascii=False))
        try:
            while True:
                raw = await websocket.receive_text()
                if not raw.strip():
                    continue
                message = json.loads(raw)
                if message.get("type") == "ping":
                    await websocket.send_text(json.dumps({"type": "pong"}, ensure_ascii=False))
                elif message.get("type") == "hello":
                    hello_sequence = _coerce_last_sequence(message.get("last_sequence"))
                    await websocket.send_text(
                        json.dumps(
                            self.snapshot(hello_sequence),
                            ensure_ascii=False,
                        )
                    )
                elif message.get("type") == "control":
                    await self._handle_control(message.get("action", ""), message)
        except Exception:
            pass
        finally:
            self._clients.discard(websocket)

    def snapshot(self, last_sequence: int | None) -> dict[str, Any]:
        base: dict[str, Any] = (
            self._session.snapshot()
            if self._session is not None
            else {
                "event_type": "snapshot",
                "payload": {
                    "status": None,
                    "latest_triplet": None,
                    "latest_result": None,
                    "latest_source_health": None,
                    "recent_events": [],
                },
            }
        )
        session_id = self._session.session_id if self._session is not None else "no-session"
        base["schema_version"] = "ws-event.v1"
        base["session_id"] = session_id
        base["sequence"] = self._sequence
        base["emitted_at"] = _now_iso()
        payload: dict[str, Any] = base["payload"]
        payload["catch_up"] = []
        if last_sequence is not None:
            payload["catch_up"] = [
                event
                for event in self._buffer
                if event["session_id"] == session_id and event["sequence"] > last_sequence
            ]
        base["payload"] = payload
        return base

    async def _handle_control(self, action: str, message: dict[str, Any]) -> None:
        session = self._session
        if session is None:
            return
        if action == "pause":
            session.pause()
        elif action == "resume":
            session.resume()
        elif action == "step":
            await session.step_and_wait(int(message.get("frames", 1)))
        elif action == "seek":
            session.seek(float(message.get("seconds", 0.0)))
        elif action == "rate":
            session.set_rate(float(message.get("rate", 1.0)))
        elif action == "record":
            await session.toggle_recording()
        elif action == "start":
            session.start()
        elif action == "stop":
            await session.stop()


def _parse_ms(iso: str) -> float:
    try:
        parsed = datetime.fromisoformat(iso)
        return parsed.timestamp() * 1000
    except ValueError:
        return 0.0


def _coerce_last_sequence(value: Any) -> int | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed >= 0 else None


_hub: StreamHub | None = None


def get_hub() -> StreamHub:
    global _hub
    if _hub is None:
        _hub = StreamHub()
    return _hub


def reset_hub_for_testing() -> StreamHub:
    global _hub
    _hub = StreamHub()
    return _hub


# Backwards-compatible alias used by earlier phase tests.
ReplayStreamSession = StreamSession
