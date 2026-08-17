"""Host-side C compilation fixtures for firmware contract tests."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SHARED = ROOT / "firmware" / "shared"
HOST_TEST = ROOT / "firmware" / "host_test"


def _cc() -> str:
    for name in ("cc", "clang", "gcc"):
        path = shutil.which(name)
        if path:
            return path
    pytest.skip("no C compiler available for host golden tests")
    return ""


def _compile(tmp_path: Path, sources: list[Path], exe_name: str) -> Path:
    cc = _cc()
    exe = tmp_path / exe_name
    subprocess.run(
        [
            cc,
            "-std=c11",
            "-Wall",
            "-Wextra",
            "-Werror",
            "-Wpedantic",
            f"-I{SHARED / 'include'}",
            *map(str, sources),
            "-o",
            str(exe),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    return exe


@pytest.fixture(scope="session")
def wire_golden_stdout(tmp_path_factory: pytest.TempPathFactory) -> str:
    tmp = tmp_path_factory.mktemp("wire_golden")
    exe = _compile(
        tmp,
        [
            HOST_TEST / "wire_golden_test.c",
            SHARED / "wire_protocol.c",
            SHARED / "crc32.c",
        ],
        "wire_golden_test",
    )
    result = subprocess.run([str(exe)], check=True, capture_output=True, text=True)
    return result.stdout


@pytest.fixture(scope="session")
def frame_pool_ok(tmp_path_factory: pytest.TempPathFactory) -> bool:
    tmp = tmp_path_factory.mktemp("frame_pool")
    exe = _compile(
        tmp,
        [HOST_TEST / "frame_pool_test.c", SHARED / "frame_pool.c"],
        "frame_pool_test",
    )
    subprocess.run([str(exe)], check=True, capture_output=True, text=True)
    return True
