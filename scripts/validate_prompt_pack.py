#!/usr/bin/env python3
"""Validate the prompt-engineering package without third-party dependencies."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

REQUIRED_FILES = [
    "README.md",
    "AGENTS.md",
    "PROJECT_INDEX.yaml",
    "STATE.md",
    "TASKS.md",
    "RUN_ORDER.md",
    "docs/PRODUCT_SPEC.md",
    "docs/ARCHITECTURE.md",
    "docs/HARDWARE_AND_CALIBRATION.md",
    "docs/DATA_CONTRACTS.md",
    "docs/OPEN_SOURCE_AUDIT.md",
    "docs/AGENT_COUNCIL.md",
    "docs/WEB_UX_SPEC.md",
    "docs/ACCEPTANCE_TESTS.md",
    "schemas/csi_frame.schema.json",
    "schemas/signal_triplet.schema.json",
    "templates/.env.example",
]

PHASE_FILES = [
    "prompts/00_MASTER_BUILD.md",
    "prompts/01_BOOTSTRAP.md",
    "prompts/02_FIRMWARE.md",
    "prompts/03_INGEST_AND_REPLAY.md",
    "prompts/04_SIGNAL_PIPELINE.md",
    "prompts/05_CALIBRATION_AND_DATASET.md",
    "prompts/06_THREE_SIGNALS.md",
    "prompts/07_AGENT_COUNCIL.md",
    "prompts/08_WEB_EXPERIENCE.md",
    "prompts/09_MULTIMODAL_OUTPUT.md",
    "prompts/10_END_TO_END.md",
    "prompts/11_HARDWARE_VALIDATION.md",
    "prompts/12_HARDEN_AND_HANDOFF.md",
]


def fail(message: str, errors: list[str]) -> None:
    errors.append(message)


def validate_files(errors: list[str]) -> None:
    for relative in REQUIRED_FILES + PHASE_FILES:
        path = ROOT / relative
        if not path.is_file():
            fail(f"missing required file: {relative}", errors)
        elif path.stat().st_size == 0:
            fail(f"empty required file: {relative}", errors)


def validate_json(errors: list[str]) -> None:
    for relative in ("schemas/csi_frame.schema.json", "schemas/signal_triplet.schema.json"):
        try:
            parsed = json.loads((ROOT / relative).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            fail(f"invalid JSON in {relative}: {exc}", errors)
            continue
        if parsed.get("type") != "object" or "$schema" not in parsed:
            fail(f"schema lacks object type or $schema: {relative}", errors)


def validate_prompts(errors: list[str]) -> None:
    common_headings = ("## Role", "## Goal", "## Acceptance gate")
    for index, relative in enumerate(PHASE_FILES):
        text = (ROOT / relative).read_text(encoding="utf-8")
        if index == 0:
            for heading in ("## Role", "## Goal", "## Success criteria", "## Stop rules"):
                if heading not in text:
                    fail(f"{relative} missing heading {heading}", errors)
            continue
        expected_prefix = f"# Phase {index:02d}"
        if not text.startswith(expected_prefix):
            fail(f"{relative} must start with {expected_prefix}", errors)
        for heading in (*common_headings, "## Read first", "## Completion"):
            if heading not in text:
                fail(f"{relative} missing heading {heading}", errors)
        if "STATE.md" not in (ROOT / "AGENTS.md").read_text(encoding="utf-8"):
            fail("AGENTS.md must require STATE.md", errors)


def validate_index(errors: list[str]) -> None:
    index_text = (ROOT / "PROJECT_INDEX.yaml").read_text(encoding="utf-8")
    listed = re.findall(r"^\s+- (prompts/[^\s]+\.md)\s*$", index_text, flags=re.MULTILINE)
    expected = PHASE_FILES[1:]
    if listed != expected:
        fail(f"PROJECT_INDEX phase order mismatch: expected {expected}, got {listed}", errors)


def validate_truth_contract(errors: list[str]) -> None:
    combined = "\n".join(
        (ROOT / relative).read_text(encoding="utf-8")
        for relative in ("README.md", "AGENTS.md", "docs/PRODUCT_SPEC.md", "docs/AGENT_COUNCIL.md")
    )
    required_phrases = (
        "final_claim_confidence <= sensor_confidence_cap",
        "Agent",
        "unknown",
        "非真实影像",
    )
    for phrase in required_phrases:
        if phrase not in combined:
            fail(f"truth contract phrase missing: {phrase}", errors)


def main() -> int:
    errors: list[str] = []
    validate_files(errors)
    if not errors:
        validate_json(errors)
        validate_prompts(errors)
        validate_index(errors)
        validate_truth_contract(errors)

    if errors:
        print("Prompt pack validation FAILED")
        for error in errors:
            print(f"- {error}")
        return 1

    markdown_count = len(list(ROOT.rglob("*.md")))
    total_bytes = sum(path.stat().st_size for path in ROOT.rglob("*") if path.is_file())
    print("Prompt pack validation PASSED")
    print(f"- phases: {len(PHASE_FILES) - 1} + master")
    print(f"- markdown files: {markdown_count}")
    print(f"- total bytes: {total_bytes}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
