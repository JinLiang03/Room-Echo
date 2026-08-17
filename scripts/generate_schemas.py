#!/usr/bin/env python3
"""Generate JSON Schemas from the Pydantic contract models (source of truth)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from wifi_contracts.registry import CONTRACT_SCHEMAS, schema_for

ROOT = Path(__file__).resolve().parents[1]
SCHEMAS_DIR = ROOT / "schemas"
DIALECT = "https://json-schema.org/draft/2020-12/schema"


def render_schema(name: str) -> str:
    schema = schema_for(name)
    doc = {"$schema": DIALECT, **schema}
    return json.dumps(doc, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="fail on drift without writing files",
    )
    args = parser.parse_args()

    drifted: list[str] = []
    for name, _model in CONTRACT_SCHEMAS:
        path = SCHEMAS_DIR / f"{name}.schema.json"
        rendered = render_schema(name)
        if args.check:
            if not path.is_file() or path.read_text(encoding="utf-8") != rendered:
                drifted.append(str(path))
        else:
            path.write_text(rendered, encoding="utf-8")

    if args.check and drifted:
        print("Schema drift detected:")
        for path in drifted:
            print(f"- {path}")
        return 1

    action = "Verified" if args.check else "Wrote"
    print(f"{action} {len(CONTRACT_SCHEMAS)} JSON Schemas in {SCHEMAS_DIR}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
