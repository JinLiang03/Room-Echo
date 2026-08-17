#!/usr/bin/env python3
"""Render release_report.json + audits into a single HTML summary."""

from __future__ import annotations

import argparse
import html
import json
from pathlib import Path


def render(report: dict, audits: dict[str, dict]) -> str:
    rows = ""
    for gate in report.get("gates", []):
        status = gate.get("status", "?")
        rows += (
            f"<tr><td><span class='s s-{status}'>{status}</span></td>"
            f"<td>{html.escape(gate.get('name', ''))}</td>"
            f"<td><code>{html.escape(gate.get('command') or '')}</code></td>"
            f"<td>{gate.get('elapsed_s') or '—'}</td>"
            f"<td><pre>{html.escape((gate.get('detail') or '')[:240])}</pre></td>"
            f"<td>{html.escape(str(gate.get('artifact') or ''))}</td></tr>"
        )
    audit_html = ""
    for name, data in audits.items():
        passed = data.get("passed")
        summary = {
            "sbom": f"{len(data.get('python', []))} python + {len(data.get('web', []))} web",
            "license_audit": f"copyleft flags = {len(data.get('copyleft_flags', []))}",
            "security_audit": (
                f"secrets = {len(data.get('secret_findings', []))}, "
                f"logs clean = {data.get('log_redaction', {}).get('passed')}"
            ),
            "claim_audit": f"findings = {len(data.get('findings', []))}",
        }.get(name, "")
        audit_html += (
            f"<tr><td>{html.escape(name)}</td>"
            f"<td>{'passed' if passed else 'failed/blocked'}</td>"
            f"<td>{html.escape(summary)}</td></tr>"
        )
    summary = report.get("summary", {})
    return f"""<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8">
<title>Release report — WiFi Spatial Council</title>
<style>body{{font-family:system-ui,sans-serif;max-width:1100px;margin:2rem auto;
padding:0 1rem}}table{{border-collapse:collapse;width:100%;font-size:.8rem}}
th,td{{border:1px solid #ccc;padding:.3rem .5rem;vertical-align:top;text-align:left}}
pre{{margin:0;white-space:pre-wrap}}h2{{margin-top:2rem}}
.s{{padding:.1rem .5rem;border-radius:999px;font-weight:600}}
.s-passed{{background:#d1fae5;color:#047857}}
.s-failed{{background:#fee2e2;color:#b91c1c}}
.s-not_run{{background:#e5e7eb;color:#374151}}
.s-blocked_by_hardware{{background:#fef3c7;color:#92400e}}</style></head><body>
<h1>Release report — WiFi Spatial Council</h1>
<p>mode <code>{html.escape(str(report.get('mode')))}</code> · generated
<code>{html.escape(str(report.get('generated_at')))}</code> ·
release_candidate <strong>{report.get('release_candidate')}</strong></p>
<p>summary: passed {summary.get('passed')} · failed {summary.get('failed')} ·
not_run {summary.get('not_run')} · blocked_by_hardware
{summary.get('blocked_by_hardware')}</p>
<h2>Audits</h2><table><thead><tr><th>audit</th><th>status</th><th>summary</th>
</tr></thead><tbody>{audit_html}</tbody></table>
<h2>Gates</h2><table><thead><tr><th>status</th><th>name</th><th>command</th>
<th>elapsed_s</th><th>detail</th><th>artifact</th></tr></thead>
<tbody>{rows}</tbody></table>
</body></html>
"""


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", default="artifacts/release_report.json", type=Path)
    parser.add_argument("--output", default="artifacts/release_report.html", type=Path)
    parser.add_argument("--release-dir", default="artifacts/release", type=Path)
    args = parser.parse_args(argv)

    report = json.loads(args.report.read_text(encoding="utf-8"))
    audits: dict[str, dict] = {}
    for name in ("sbom", "license_audit", "security_audit", "claim_audit"):
        path = args.release_dir / f"{name}.json"
        if path.is_file():
            audits[name] = json.loads(path.read_text(encoding="utf-8"))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(render(report, audits), encoding="utf-8")
    print(f"report html: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
