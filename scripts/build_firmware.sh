#!/usr/bin/env bash
#
# Build both ESP32 firmware targets and write a build manifest.
#
# Requires an ESP-IDF environment (>=5.5,<6). Resolution order:
#   1. `idf.py` already on PATH;
#   2. $IDF_PATH pointing at a checkout with export.sh;
#   3. auto-discovery under $HOME/esp/esp-idf-v* (highest version first).
# Exits with a non-zero code and an exact blocker message when ESP-IDF is not
# available — the build result is never fabricated.
#
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MANIFEST_DIR="$ROOT/firmware/build"
MANIFEST="$MANIFEST_DIR/manifest.json"

# Commit of the esp-csi source review; pinned for reproducibility.
ESP_CSI_COMMIT="8633d67152db2808f141cc1595970aa9cf406045"

# Target board; ESP32-S3 is the documented recommendation.
WSC_TARGET="${WSC_TARGET:-esp32s3}"

echo "==> Checking ESP-IDF availability"
IDF_PY="$(command -v idf.py || true)"
if [[ -z "$IDF_PY" && -n "${IDF_PATH:-}" && -f "$IDF_PATH/export.sh" ]]; then
  # shellcheck disable=SC1090
  source "$IDF_PATH/export.sh"
  IDF_PY="$(command -v idf.py || true)"
fi

if [[ -z "$IDF_PY" ]]; then
  # Auto-discover ESP-IDF checkouts under $HOME/esp.
  while IFS= read -r candidate; do
    if [[ -n "$candidate" && -f "$candidate/export.sh" ]]; then
      echo "==> Using ESP-IDF at $candidate"
      # shellcheck disable=SC1090
      source "$candidate/export.sh"
      IDF_PY="$(command -v idf.py || true)"
      break
    fi
  done <<< "$(ls -d "$HOME"/esp/esp-idf-v* 2>/dev/null | sort -V -r || true)"
fi

if [[ -z "$IDF_PY" ]]; then
  echo "BLOCKED: ESP-IDF is not available on this machine." >&2
  echo "Exact blocker: no idf.py on PATH, no IDF_PATH, no ESP-IDF toolchain." >&2
  echo "Install ESP-IDF >=5.5,<6 (https://docs.espressif.com/projects/esp-idf/) and re-run:" >&2
  echo "  make firmware-build" >&2
  exit 2
fi

IDF_VERSION="$(idf.py --version)"
IDF_GIT_COMMIT="unknown"
if [[ -n "${IDF_PATH:-}" && -d "$IDF_PATH/.git" ]]; then
  IDF_GIT_COMMIT="$(git -C "$IDF_PATH" rev-parse HEAD)"
fi

export IDF_VERSION IDF_GIT_COMMIT ESP_CSI_COMMIT WSC_TARGET
export WSC_FW_VERSION="0.1.0"

for project in csi_tx csi_rx; do
  echo "==> Building $project (target $WSC_TARGET)"
  (
    cd "$ROOT/firmware/$project"
    idf.py set-target "$WSC_TARGET"
    idf.py build
  )
done

mkdir -p "$MANIFEST_DIR"
python3 - "$MANIFEST" "$ROOT" <<'PY'
import json
import os
import sys
import time
from pathlib import Path

root = Path(sys.argv[2])

manifest = {
    "schema_version": "1.0.0",
    "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    "esp_idf_version": os.environ.get("IDF_VERSION", ""),
    "esp_idf_git_commit": os.environ.get("IDF_GIT_COMMIT", ""),
    "esp_csi_commit": os.environ.get("ESP_CSI_COMMIT", ""),
    "target": os.environ.get("WSC_TARGET", "esp32s3"),
    "firmware_version": os.environ.get("WSC_FW_VERSION", ""),
    "projects": ["csi_tx", "csi_rx"],
    "sizes": {},
}
for project in ("csi_tx", "csi_rx"):
    binary = root / "firmware" / project / "build" / f"{project}.bin"
    manifest["sizes"][project] = {
        "app_binary_bytes": binary.stat().st_size,
    }

with open(sys.argv[1], "w", encoding="utf-8") as fh:
    json.dump(manifest, fh, indent=2, sort_keys=True)
    fh.write("\n")
PY

echo "==> Wrote $MANIFEST"
echo "Build finished for target $WSC_TARGET (built, not flashed)."
