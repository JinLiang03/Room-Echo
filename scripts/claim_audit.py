#!/usr/bin/env python3
"""Claim review: scan user-facing text for overclaim phrasing (Phase 12)."""

from __future__ import annotations

import argparse
import json
import re
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# (reason, pattern). A hit is a finding unless the line is a documented
# negation (contains a denial marker within a few chars) or is inside an
# intentional demo fixture (mock overreach), which is labeled as rejected.
PATTERNS: list[tuple[str, str]] = [
    ("perfect_imaging", r"完美(成像|透视)|camera-equivalent"),
    ("wall_presence", r"墙后(有|能|看到)|穿墙(看|检测)|透过墙"),
    ("person_count", r"发现.{0,6}人|两个人|三个人"),
    ("identity", r"人的身份|身份识别|确认.{0,6}身份|是谁"),
    ("pose", r"人体姿态|姿态识别|坐姿|站姿|手势识别"),
    ("health", r"心率|呼吸率|血压|健康风险|危险行为"),
    ("metric_depth", r"\d+(?:\.\d+)?\s*(?:米|meters?)\b|三维重建|深度图"),
    ("room_generalization", r"跨房间|任意房间|universal"),
]

NEGATION = re.compile(r"(非|不是|不承诺|不属于|禁止|不得|拒绝|不能|not |no |never)")


def audit(roots: list[Path], out: Path) -> int:
    findings: list[dict] = []
    scanned = 0
    for root in roots:
        for path in sorted(root.rglob("*")):
            if not path.is_file() or path.suffix not in {".md", ".ts", ".tsx", ".py", ".json", ".html"}:
                continue
            if any(part.startswith((".", "node_modules", "dist", "build", "__pycache__")) for part in path.parts):
                continue
            if (
                "policy_corpus" in path.name
                or path.name == "claim_audit.py"
                or path == out
                or (str(path).endswith("lib/story.ts"))
            ):
                continue
            try:
                text = path.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            for lineno, line in enumerate(text.splitlines(), start=1):
                scanned += 1
                for reason, pattern in PATTERNS:
                    match = re.search(pattern, line, re.IGNORECASE)
                    if not match:
                        continue
                    window = line[max(0, match.start() - 20): match.end() + 20]
                    if NEGATION.search(window):
                        continue
                    findings.append(
                        {
                            "file": str(path.relative_to(ROOT)),
                            "line": lineno,
                            "reason": reason,
                            "match": match.group(0),
                            "line_text": line.strip()[:160],
                        }
                    )
    report = {
        "schema_version": "claim-audit.v1",
        "generated_at": datetime.now(UTC).isoformat(),
        "scanned_lines": scanned,
        "findings": findings,
        "passed": not findings,
        "exclusions": [
            "apps/web/src/lib/story.ts — controlled demo overreach fixtures "
            "that the PolicyArbiter rejects on purpose (covered by "
            "tests/council/test_policy_corpus.py and the rejected story state)",
        ],
    }
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    for finding in findings:
        print(
            f"{finding['file']}:{finding['line']} [{finding['reason']}] "
            f"{finding['line_text']}"
        )
    print(f"claim audit: {len(findings)} findings, {scanned} lines scanned -> {out}")
    return 0 if not findings else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", default="artifacts/release/claim_audit.json", type=Path)
    args = parser.parse_args(argv)
    return audit(
        [
            ROOT / "README.md",
            ROOT / "README-OPERATOR.md",
            ROOT / "apps" / "web" / "src",
            ROOT / "artifacts" / "release_report.json",
            ROOT / "hardware",
        ],
        args.output,
    )


if __name__ == "__main__":
    raise SystemExit(main())
