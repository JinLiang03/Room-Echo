"""Release evidence must fail closed when required metrics are absent."""

from __future__ import annotations

from scripts.package_release import ROOT, _include
from scripts.verify_release import soak_gate_status


def _soak(**overrides: object) -> dict[str, object]:
    report: dict[str, object] = {
        "duration_s": 3600.0,
        "crashes": 0,
        "queue_bounded": True,
        "rss_growth_under_10pct": True,
        "latency_p95_under_300ms": True,
    }
    report.update(overrides)
    return report


def test_soak_gate_requires_full_duration_and_all_metrics() -> None:
    assert soak_gate_status(None) == "not_run"
    assert soak_gate_status(_soak(duration_s=3599.9)) == "not_run"
    assert soak_gate_status(_soak()) == "passed"


def test_soak_gate_fails_invalid_memory_or_latency_evidence() -> None:
    assert soak_gate_status(_soak(rss_growth_under_10pct=False)) == "failed"
    assert soak_gate_status(_soak(latency_p95_under_300ms=False)) == "failed"
    assert soak_gate_status(_soak(latency_p95_under_300ms=None)) == "failed"


def test_release_archive_excludes_sensitive_raw_captures() -> None:
    assert not _include(ROOT / "data" / "raw" / "live-session" / "raw.csi.zst")
    assert _include(ROOT / "data" / "fixtures" / "demo_2min" / "raw.csi.zst")


def test_release_archive_excludes_local_env_but_keeps_example() -> None:
    assert not _include(ROOT / ".env")
    assert not _include(ROOT / ".env.production.local")
    assert _include(ROOT / ".env.example")
