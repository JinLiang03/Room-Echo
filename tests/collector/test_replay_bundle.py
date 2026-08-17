"""Record → verify → replay equivalence and replay-bundle security."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import zstandard as zstd
from wifi_collector.mock_source import MockFrameSource
from wifi_collector.recorder import RecordSession
from wifi_collector.replay_bundle import (
    CHECKSUMS_FILE,
    MANIFEST_FILE,
    RAW_FILE,
    BundleVerifier,
)
from wifi_collector.replay_source import ReplayFrameSource
from wifi_contracts import NormalizedCsiFrame


async def _record_mock(
    raw_root: Path,
    *,
    duration_s: float = 0.3,
    seed: int = 9,
) -> Path:
    source = MockFrameSource(
        scenario="walk_through",
        seed=seed,
        duration_s=duration_s,
        real_time=False,
        session_id="sess-eq",
    )
    session = RecordSession(
        source=source,
        session_id="sess-eq",
        raw_root=raw_root,
    )
    try:
        return await session.run()
    finally:
        await source.close()


async def _replay_frames(bundle: Path) -> list[dict]:
    source = ReplayFrameSource(bundle, real_time=False)
    frames = []
    async for frame in source.frames():
        frames.append(frame.model_dump(mode="json"))
    await source.close()
    return frames


async def _wait_for_count(values: list[NormalizedCsiFrame], count: int) -> None:
    for _ in range(100):
        if len(values) >= count:
            return
        await asyncio.sleep(0.01)
    raise AssertionError(f"timed out waiting for {count} frames; got {len(values)}")


def _normalize_mode(frames: list[dict], mode: str) -> list[dict]:
    for frame in frames:
        frame["source_mode"] = mode
    return sorted(frames, key=lambda f: (f["seq"], f["link_id"]))


def test_record_verify_replay_equivalent(tmp_path: Path) -> None:
    bundle = asyncio.run(_record_mock(tmp_path))

    result = BundleVerifier(bundle).verify()
    assert result.ok, result.errors
    assert result.manifest is not None
    assert result.manifest.status == "complete"

    replayed = asyncio.run(_replay_frames(bundle))
    assert len(replayed) > 0

    async def _original() -> list[dict]:
        source = MockFrameSource(
            scenario="walk_through",
            seed=9,
            duration_s=0.3,
            real_time=False,
            session_id="sess-eq",
        )
        frames = []
        async for frame in source.frames():
            frames.append(frame.model_dump(mode="json"))
        await source.close()
        return frames

    original = asyncio.run(_original())
    assert len(original) == len(replayed)
    # source_mode differs by contract (replay labels frames "replay").
    assert _normalize_mode(original, "replay") == _normalize_mode(replayed, "replay")


def test_seek_repositions_an_active_reader_including_backwards(tmp_path: Path) -> None:
    bundle = asyncio.run(_record_mock(tmp_path))

    async def check() -> None:
        source = ReplayFrameSource(bundle, real_time=False)
        iterator = source.frames().__aiter__()
        initial = [await anext(iterator) for _ in range(20)]
        assert initial[-1].seq == 9

        previous_revision = source.control_revision
        source.seek(0)
        rewound = await asyncio.wait_for(anext(iterator), timeout=1.0)
        assert (rewound.seq, rewound.link_id) == (0, "rx-a")
        assert source.control_revision == previous_revision + 1
        assert source.frame_revision == source.control_revision
        assert source.position_s == 0.0

        source.seek(0.05)
        positioned = await asyncio.wait_for(anext(iterator), timeout=1.0)
        assert (positioned.seq, positioned.link_id) == (5, "rx-a")
        assert positioned.device_ts_us == 50_000
        assert source.position_s == 0.05
        await source.close()

    asyncio.run(check())


def test_step_while_paused_yields_exact_count_and_stays_paused(
    tmp_path: Path,
) -> None:
    bundle = asyncio.run(_record_mock(tmp_path))

    async def check() -> None:
        source = ReplayFrameSource(bundle, rate=4.0, real_time=True)
        await source.pause()
        frames: list[NormalizedCsiFrame] = []

        async def consume() -> None:
            async for frame in source.frames():
                frames.append(frame)

        task = asyncio.create_task(consume())
        await asyncio.sleep(0.05)
        assert frames == []

        source.step(5)
        await _wait_for_count(frames, 5)
        await asyncio.sleep(0.05)
        assert len(frames) == 5
        assert source.is_paused is True
        assert task.done() is False

        # A second command advances relative to the current cursor and does
        # not terminate the async iterator when its token budget is spent.
        source.step(3)
        await _wait_for_count(frames, 8)
        await asyncio.sleep(0.05)
        assert len(frames) == 8
        assert source.is_paused is True
        assert task.done() is False

        await source.resume()
        await _wait_for_count(frames, 10)
        assert source.is_paused is False
        await source.close()
        await task

    asyncio.run(check())


def test_seek_while_paused_does_not_implicitly_resume(tmp_path: Path) -> None:
    bundle = asyncio.run(_record_mock(tmp_path))

    async def check() -> None:
        source = ReplayFrameSource(bundle, real_time=False)
        await source.pause()
        frames: list[NormalizedCsiFrame] = []

        async def consume() -> None:
            async for frame in source.frames():
                frames.append(frame)

        task = asyncio.create_task(consume())
        source.seek(0.1)
        await asyncio.sleep(0.05)
        assert frames == []
        assert source.is_paused is True

        source.step(1)
        await _wait_for_count(frames, 1)
        frame = frames[0]
        assert frame.seq == 10
        assert source.position_s == 0.1
        assert source.is_paused is True
        await source.close()
        await task

    asyncio.run(check())


def test_checksum_mismatch_rejected(tmp_path: Path) -> None:
    bundle = asyncio.run(_record_mock(tmp_path))
    checksums = bundle / CHECKSUMS_FILE
    lines = checksums.read_text(encoding="utf-8").splitlines()
    lines[0] = "0" * 64 + "  " + lines[0].split("  ", 1)[1]
    checksums.write_text("\n".join(lines) + "\n", encoding="utf-8")
    result = BundleVerifier(bundle).verify()
    assert not result.ok
    assert any("checksum mismatch" in error for error in result.errors)


def test_missing_file_rejected(tmp_path: Path) -> None:
    bundle = asyncio.run(_record_mock(tmp_path))
    (bundle / RAW_FILE).unlink()
    result = BundleVerifier(bundle).verify()
    assert not result.ok
    assert any("missing file" in error for error in result.errors)


def test_path_traversal_rejected(tmp_path: Path) -> None:
    bundle = asyncio.run(_record_mock(tmp_path))
    manifest_path = bundle / MANIFEST_FILE
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["files"] = ["../evil", "raw.csi.zst", "events.jsonl"]
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    result = BundleVerifier(bundle).verify()
    assert not result.ok


def test_absolute_path_rejected(tmp_path: Path) -> None:
    bundle = asyncio.run(_record_mock(tmp_path))
    manifest_path = bundle / MANIFEST_FILE
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["files"] = ["/etc/passwd", "raw.csi.zst", "events.jsonl"]
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    result = BundleVerifier(bundle).verify()
    assert not result.ok


def test_symlink_escape_rejected(tmp_path: Path) -> None:
    bundle = asyncio.run(_record_mock(tmp_path))
    outside = tmp_path / "outside.bin"
    outside.write_bytes(b"x" * 16)
    link = bundle / "escape"
    link.symlink_to(outside)
    manifest_path = bundle / MANIFEST_FILE
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["files"] = ["escape", "raw.csi.zst", "events.jsonl"]
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    result = BundleVerifier(bundle).verify()
    assert not result.ok
    assert any("escapes" in error for error in result.errors)


def test_zip_bomb_style_raw_rejected(tmp_path: Path) -> None:
    bundle = asyncio.run(_record_mock(tmp_path))
    bomb = zstd.ZstdCompressor(level=1).compress(b"\x00" * (16 << 20))
    (bundle / RAW_FILE).write_bytes(bomb)
    result = BundleVerifier(bundle, max_raw_bytes=1024).verify()
    assert not result.ok
    assert any("cap" in error for error in result.errors)


def test_invalid_manifest_rejected(tmp_path: Path) -> None:
    bundle = asyncio.run(_record_mock(tmp_path))
    (bundle / MANIFEST_FILE).write_text("{not json", encoding="utf-8")
    result = BundleVerifier(bundle).verify()
    assert not result.ok


def test_incomplete_bundle_not_verified(tmp_path: Path) -> None:
    bundle = asyncio.run(_record_mock(tmp_path))
    manifest_path = bundle / MANIFEST_FILE
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["status"] = "incomplete"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    assert not BundleVerifier(bundle).verify().ok
    assert BundleVerifier(bundle, require_complete=False).verify().ok
