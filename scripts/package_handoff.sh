#!/bin/sh
# Build an offline handoff bundle for hardware testing on a colleague's Mac.
#
# The bundle keeps everything needed to run without re-installing toolchains:
#   - .venv (Python deps, incl. esptool + pyserial)  [macOS arm64 only]
#   - apps/web/node_modules                           [macOS only]
#   - firmware/*/build  ->  only flash artifacts (bootloader + app + partition
#     table + flash_args [+ elf for panic decoding]), not the 148 MB of
#     ESP-IDF intermediate objects per board
#   - source, deterministic fixtures, calibration, docs
# It excludes local raw captures plus regenerable derived logs, caches, and
# Playwright screenshots. Share a selected verified raw bundle separately.
#
# Usage: scripts/package_handoff.sh
set -eu

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PROJ="$(basename "$ROOT")"
STAMP="$(date +%Y%m%d)"
OUT_DIR="${ROOT}/artifacts/handoff"
OUT_TAR="${OUT_DIR}/wifi-spatial-council-handoff-${STAMP}.tar"
PY_DIR="$HOME/.local/share/uv/python/cpython-3.11.15-macos-aarch64-none"
STAGE_PY="${ROOT}/.handoff-python"

mkdir -p "$OUT_DIR"

cd "$ROOT"

chmod +x scripts/flash_bundle.sh
chmod +x scripts/relink_venv.sh

echo "==> packing project under $PROJ/ (excludes regenerable output)"
tar -cf "$OUT_TAR" \
  --exclude="$PROJ/data/derived" \
  --exclude="$PROJ/data/raw" \
  --exclude='*/.env*' \
  --exclude="$PROJ/.git" \
  --exclude="$PROJ/.hypothesis" \
  --exclude="$PROJ/.mypy_cache" \
  --exclude="$PROJ/.pytest_cache" \
  --exclude="$PROJ/.ruff_cache" \
  --exclude='*/__pycache__' \
  --exclude='*.pyc' \
  --exclude="$PROJ/artifacts/web" \
  --exclude="$PROJ/artifacts/handoff" \
  --exclude="$PROJ/apps/web/dist" \
  --exclude="$PROJ/apps/web/test-results" \
  --exclude="$PROJ/apps/web/playwright-report" \
  --exclude="$PROJ/apps/web/perf-debug*.mjs" \
  --exclude="$PROJ/wifi_spatial_council.egg-info" \
  --exclude='.DS_Store' \
  --exclude="$PROJ/firmware/csi_tx/build" \
  --exclude="$PROJ/firmware/csi_rx/build" \
  --exclude="$PROJ/.handoff-python" \
  -C "$ROOT/.." \
  "$PROJ"

echo "==> appending minimal firmware flash artifacts"
tar -rf "$OUT_TAR" -C "$ROOT/.." \
  "$PROJ/firmware/csi_tx/build/bootloader/bootloader.bin" \
  "$PROJ/firmware/csi_tx/build/partition_table/partition-table.bin" \
  "$PROJ/firmware/csi_tx/build/csi_tx.bin" \
  "$PROJ/firmware/csi_tx/build/flash_args" \
  "$PROJ/firmware/csi_tx/build/csi_tx.elf" \
  "$PROJ/firmware/csi_rx/build/bootloader/bootloader.bin" \
  "$PROJ/firmware/csi_rx/build/partition_table/partition-table.bin" \
  "$PROJ/firmware/csi_rx/build/csi_rx.bin" \
  "$PROJ/firmware/csi_rx/build/flash_args" \
  "$PROJ/firmware/csi_rx/build/csi_rx.elf"

echo "==> bundling self-contained CPython runtime (.handoff-python, macOS arm64)"
if [ ! -d "$PY_DIR" ]; then
  echo "error: bundled runtime source not found: $PY_DIR" >&2
  exit 1
fi
rm -rf "$STAGE_PY"
cp -R "$PY_DIR" "$STAGE_PY"
tar -rf "$OUT_TAR" -C "$ROOT/.." "$PROJ/.handoff-python"
rm -rf "$STAGE_PY"

UNCOMPRESSED="$(du -h "$OUT_TAR" | awk '{print $1}')"
echo "==> uncompressed handoff bundle: $UNCOMPRESSED"
echo "==> compressing (gzip -9, may take a few minutes)"
gzip -9 -f "$OUT_TAR"
OUT_GZ="${OUT_TAR}.gz"
CHECKSUM="${OUT_GZ}.sha256"
shasum -a 256 "$OUT_GZ" > "$CHECKSUM"
ls -lh "$OUT_GZ" | awk '{print "final bundle:", $9, "(" $5 ")"}'
echo "checksum: $CHECKSUM"
echo "colleague steps: extract -> scripts/relink_venv.sh -> scripts/flash_bundle.sh"
