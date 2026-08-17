"""Calibration report generation (JSON + static HTML)."""

from __future__ import annotations

import html
import json
from pathlib import Path
from typing import Any


def _window_scores(windows: list[Any]) -> dict[str, list[float]]:
    motion: list[float] = []
    occupancy: list[float] = []
    depth: list[float] = []
    for window in windows:
        for feature in window.links.values():
            motion.append(feature.temporal_diff_rms)
            occupancy.append(feature.amplitude_anomaly_ratio)
        if window.paired is not None:
            depth.append(window.paired.amplitude_shape_asymmetry)
    return {"motion": motion, "occupancy": occupancy, "depth": depth}


def build_report(session: Any, profile: Any) -> dict[str, Any]:
    """Assemble the calibration report payload."""
    trials = []
    for trial_id, trial in session.trials.items():
        trials.append(
            {
                "trial_id": trial_id,
                "step": trial.step,
                "labels": trial.label,
                "random_order_index": trial.random_order_index,
                "windows": len(session.windows_by_trial.get(trial_id, [])),
                "curves": _window_scores(session.windows_by_trial.get(trial_id, [])),
            }
        )
    profile_dict = profile.model_dump(mode="json")
    return {
        "schema_version": "calibration-report.v1",
        "profile_id": profile.profile_id,
        "room_id": profile.room_id,
        "simulated": profile.simulated,
        "state": profile.state,
        "feature_version": profile.feature_version,
        "estimator_version": profile.estimator_version,
        "checksum": profile.checksum,
        "train_trial_ids": profile.training_trial_ids,
        "validation_trial_ids": profile.validation_trial_ids,
        "metrics": profile_dict.get("metrics"),
        "trials": trials,
        "limitations": [
            "occupancy labels are scene disturbance grades, not person counts",
            "depth points are ordinal along the preset axis, not metric depth",
            "single-RX windows yield depth unknown (no fabricated pairing)",
            "simulated metrics are NOT hardware evidence" if profile.simulated
            else "metrics were produced from real hardware recordings",
        ],
    }


def render_html(report: dict[str, Any]) -> str:
    metrics = report.get("metrics") or {}
    simulated = report.get("simulated", False)
    rows = "".join(
        f"<tr><td>{trial['trial_id']}</td><td>{trial['step']}</td>"
        f"<td>{trial['random_order_index']}</td><td>{trial['windows']}</td></tr>"
        for trial in report.get("trials", [])
    )
    return f"""<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8">
<title>Calibration report — {html.escape(report['profile_id'])}</title>
<style>body{{font-family:system-ui,sans-serif;max-width:900px;margin:2rem auto;
padding:0 1rem;color:#111}}table{{border-collapse:collapse;width:100%}}
th,td{{border:1px solid #ccc;padding:.35rem .5rem;text-align:left}}
.badge{{display:inline-block;padding:.15rem .6rem;border-radius:999px;
background:#fde68a;font-weight:600}}
.badge-live{{background:#bbf7d0}}</style></head><body>
<h1>Calibration report</h1>
<p>profile <code>{html.escape(report['profile_id'])}</code> · room
<code>{html.escape(report['room_id'])}</code> ·
feature {html.escape(report['feature_version'])} ·
estimator {html.escape(report['estimator_version'])}</p>
<p><span class="badge{' badge-live' if not simulated else ''}">
{'SIMULATED — NOT HARDWARE EVIDENCE' if simulated else 'LIVE'}</span></p>
<h2>Metrics</h2>
<ul><li>motion separation: {metrics.get('motion_separation')}</li>
<li>occupancy ordinal accuracy: {metrics.get('occupancy_ordinal_accuracy')}</li>
<li>depth zone accuracy: {metrics.get('depth_monotonic_accuracy')}</li>
<li>held-out trials: {', '.join(metrics.get('held_out_trial_ids', []))}</li></ul>
<h2>Trials</h2>
<table><thead><tr><th>trial</th><th>step</th><th>random order</th>
<th>windows</th></tr></thead><tbody>{rows}</tbody></table>
<h2>Limitations</h2><ul>{''.join(f'<li>{html.escape(item)}</li>'
for item in report.get('limitations', []))}</ul>
</body></html>
"""


def write_report(
    session: Any,
    profile: Any,
    out_dir: Path,
) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    report = build_report(session, profile)
    (out_dir / "calibration_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (out_dir / "calibration_report.html").write_text(
        render_html(report),
        encoding="utf-8",
    )
    return out_dir
