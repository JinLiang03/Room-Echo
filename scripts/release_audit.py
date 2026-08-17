#!/usr/bin/env python3
"""Release audit: SBOM, licenses, secrets, CORS, log redaction (Phase 12)."""

from __future__ import annotations

import argparse
import importlib.metadata
import json
import re
import subprocess
import tomllib
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
RELEASE_DIR = ROOT / "artifacts" / "release"

# These are optional standalone command-line tools, not imported or linked by
# the runtime application. Their own copyleft terms still apply and they stay
# visible in the SBOM/tooling review, but they do not make the application
# runtime a copyleft dependency graph.
STANDALONE_COPYLEFT_TOOLS = {"esptool"}

SECRET_PATTERNS = [
    re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b"),
    re.compile(r"\bOPENAI_API_KEY\s*=\s*[A-Za-z0-9_-]{20,}\b"),
    re.compile(r"\b(?:AWS|AZURE|GITHUB)_?(?:SECRET|TOKEN|KEY)\s*=\s*[A-Za-z0-9/+]{16,}\b"),
    re.compile(r"\bpassword\s*=\s*['\"][^'\"]{8,}['\"]", re.IGNORECASE),
]

EXCLUDED_PARTS = {
    ".venv",
    "node_modules",
    "dist",
    "__pycache__",
    ".git",
    ".espressif",
    "raw.csi.zst",
}


def _uv_lock_packages() -> list[dict[str, Any]]:
    lock = tomllib.loads((ROOT / "uv.lock").read_text(encoding="utf-8"))
    packages: list[dict[str, Any]] = []
    for entry in lock.get("package", []):
        packages.append(
            {
                "name": entry.get("name"),
                "version": entry.get("version"),
                "source": (entry.get("source") or {}).get("registry"),
            }
        )
    return packages


def _web_dependencies() -> list[dict[str, Any]]:
    package = json.loads(
        (ROOT / "apps" / "web" / "package.json").read_text(encoding="utf-8")
    )
    deps: list[dict[str, Any]] = []
    for section in ("dependencies", "devDependencies"):
        for name, version in package.get(section, {}).items():
            license_name: str | None = None
            meta_path = (
                ROOT / "apps" / "web" / "node_modules" / name / "package.json"
            )
            if meta_path.is_file():
                meta = json.loads(meta_path.read_text(encoding="utf-8"))
                raw = meta.get("license") or meta.get("licenses")
                if isinstance(raw, str):
                    license_name = raw
                elif isinstance(raw, list) and raw:
                    license_name = raw[0].get("type") if isinstance(raw[0], dict) else str(raw[0])
            deps.append(
                {
                    "name": name,
                    "version": version,
                    "group": section,
                    "license": license_name,
                }
            )
    return deps


def _python_licenses(packages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for package in packages:
        name = package["name"]
        if not name:
            continue
        license_name: str | None = None
        try:
            meta = importlib.metadata.metadata(name)
            classifiers = meta.get_all("Classifier") or []
            license_classifiers = [
                c.split("::")[-1].strip()
                for c in classifiers
                if c.startswith("License ::")
            ]
            try:
                raw = meta["License"] or None
            except KeyError:
                raw = None
            if license_classifiers:
                license_name = license_classifiers[0]
            elif raw and len(raw) < 200:
                license_name = raw.strip()
            elif raw:
                license_name = "see-metadata-text"
        except importlib.metadata.PackageNotFoundError:
            license_name = None
        rows.append(
            {
                "name": name,
                "version": package.get("version"),
                "source": package.get("source"),
                "license": license_name,
            }
        )
    return rows


def _partition_copyleft_flags(
    rows: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    flags = [
        row
        for row in rows
        if row.get("license")
        and any(
            marker in str(row["license"]).upper()
            for marker in ("GPL", "AGPL", "LGPL")
        )
    ]
    runtime_flags = [
        row for row in flags if row.get("name") not in STANDALONE_COPYLEFT_TOOLS
    ]
    tooling_review = [
        {**row, "scope": "standalone-development-tool"}
        for row in flags
        if row.get("name") in STANDALONE_COPYLEFT_TOOLS
    ]
    return runtime_flags, tooling_review


def _secret_scan_candidates(root: Path) -> list[Path]:
    """Use the same Git-visible scope as release packaging when available."""
    if root.resolve() == ROOT.resolve():
        result = subprocess.run(
            [
                "git",
                "-C",
                str(root),
                "ls-files",
                "-z",
                "--cached",
                "--others",
                "--exclude-standard",
            ],
            check=False,
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode == 0:
            return [root / item for item in result.stdout.split("\0") if item]
    return list(root.rglob("*"))


def _scan_secrets(root: Path = ROOT) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    for path in _secret_scan_candidates(root):
        if not path.is_file():
            continue
        if any(part in EXCLUDED_PARTS for part in path.parts):
            continue
        relative = path.relative_to(root)
        if relative.parts[:2] in {("data", "raw"), ("data", "derived")}:
            continue
        if path.name != ".env.example" and path.suffix not in {
            ".py",
            ".ts",
            ".tsx",
            ".json",
            ".toml",
            ".yaml",
            ".yml",
            ".md",
            ".sh",
            ".js",
            ".mjs",
            ".c",
            ".h",
        }:
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for lineno, line in enumerate(text.splitlines(), start=1):
            for pattern in SECRET_PATTERNS:
                if pattern.search(line):
                    findings.append(
                        {
                            "file": str(relative),
                            "line": lineno,
                            "match": pattern.pattern[:40],
                        }
                    )
    return findings


def _check_cors() -> dict[str, Any]:
    try:
        from wifi_api.app import app

        middleware = [
            getattr(m.cls, "__name__", str(m.cls)) for m in app.user_middleware
        ]
        return {
            "cors_middleware": any("CORSMiddleware" in name for name in middleware),
            "middleware": middleware,
            "note": "no CORS middleware = same-origin only (vite dev proxy)",
        }
    except Exception as exc:  # pragma: no cover
        return {"cors_middleware": None, "error": str(exc)[:200]}


def _scan_log_redaction() -> dict[str, Any]:
    findings: list[str] = []
    for path in (ROOT / "data" / "derived").rglob("*.jsonl"):
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        if "sk-" in text or "OPENAI_API_KEY" in text:
            findings.append(str(path.relative_to(ROOT)))
    return {
        "logs_scanned": len(list((ROOT / "data" / "derived").rglob("*.jsonl"))),
        "secret_findings": findings,
        "passed": not findings,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", default=RELEASE_DIR, type=Path)
    args = parser.parse_args(argv)
    out = args.output
    out.mkdir(parents=True, exist_ok=True)

    python_packages = _uv_lock_packages()
    python_licenses = _python_licenses(python_packages)
    web_deps = _web_dependencies()
    secrets = _scan_secrets()
    cors = _check_cors()
    redaction = _scan_log_redaction()

    license_flags, tooling_review = _partition_copyleft_flags(
        [*python_licenses, *web_deps]
    )
    project_license_files = sorted(
        path.name for path in ROOT.glob("LICENSE*") if path.is_file()
    )
    sbom = {
        "schema_version": "sbom.v1",
        "generated_at": datetime.now(UTC).isoformat(),
        "python": python_packages,
        "web": web_deps,
    }
    (out / "sbom.json").write_text(
        json.dumps(sbom, indent=2) + "\n", encoding="utf-8"
    )

    license_audit = {
        "schema_version": "license-audit.v1",
        "generated_at": datetime.now(UTC).isoformat(),
        "copyleft_flags": license_flags,
        "tooling_review_flags": tooling_review,
        "project_license_files": project_license_files,
        "public_publication_ready": not license_flags and bool(project_license_files),
        "passed": not license_flags,
        "note": (
            "Copyleft runtime dependencies block release. Optional standalone "
            "tools remain listed for license review and are not runtime imports. "
            "A project-level LICENSE is separately required before public publication."
        ),
    }
    (out / "license_audit.json").write_text(
        json.dumps(license_audit, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    security_audit = {
        "schema_version": "security-audit.v1",
        "generated_at": datetime.now(UTC).isoformat(),
        "secret_findings": secrets,
        "secrets_passed": not secrets,
        "cors": cors,
        "log_redaction": redaction,
        "passed": not secrets and not redaction["secret_findings"],
    }
    (out / "security_audit.json").write_text(
        json.dumps(security_audit, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    print(f"SBOM: {len(python_packages)} python + {len(web_deps)} web packages")
    print(f"license audit: copyleft flags = {len(license_flags)}")
    print(f"license audit: standalone tooling review = {len(tooling_review)}")
    print(
        "license audit: public publication ready = "
        f"{not license_flags and bool(project_license_files)}"
    )
    print(
        f"security audit: secrets = {len(secrets)}, "
        f"logs clean = {not redaction['secret_findings']}"
    )
    print(f"artifacts: {out}")
    return (
        0
        if not secrets and not license_flags and not redaction["secret_findings"]
        else 1
    )


if __name__ == "__main__":
    raise SystemExit(main())
