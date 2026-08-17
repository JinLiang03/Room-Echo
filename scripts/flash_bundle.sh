#!/bin/sh
# Flash the three prebuilt firmware images (TX + RX-A + RX-B) using esptool.
#
# No ESP-IDF toolchain is required: only the prebuilt binaries in
# firmware/*/build are needed (bootloader + app + partition table + flash_args).
#
# Usage:
#   scripts/flash_bundle.sh \
#     TX_PORT=/dev/cu.usbmodemXXXX \
#     RX_A_PORT=/dev/cu.usbmodemYYYY \
#     RX_B_PORT=/dev/cu.usbmodemZZZZ
#
# Ports must be explicit. The script never guesses devices and refuses to run
# when any port is missing.
set -eu

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PYTHON="${ROOT}/.venv/bin/python"

for arg in "$@"; do
  case "$arg" in
    TX_PORT=*) TX_PORT="${arg#TX_PORT=}" ;;
    RX_A_PORT=*) RX_A_PORT="${arg#RX_A_PORT=}" ;;
    RX_B_PORT=*) RX_B_PORT="${arg#RX_B_PORT=}" ;;
    *) echo "unknown argument: $arg" >&2; exit 2 ;;
  esac
done

if [ -z "${TX_PORT:-}" ] || [ -z "${RX_A_PORT:-}" ] || [ -z "${RX_B_PORT:-}" ]; then
  echo "error: TX_PORT, RX_A_PORT and RX_B_PORT are all required." >&2
  echo "Usage: scripts/flash_bundle.sh TX_PORT=... RX_A_PORT=... RX_B_PORT=..." >&2
  exit 2
fi

if [ ! -x "$PYTHON" ]; then
  echo "error: venv python not found at $PYTHON (run 'uv sync' first)" >&2
  exit 1
fi

flash_board() {
  label="$1"
  port="$2"
  build_dir="$3"
  if [ ! -f "$build_dir/flash_args" ] || [ ! -f "$build_dir/bootloader/bootloader.bin" ]; then
    echo "error: missing flash artifacts for $label in $build_dir" >&2
    exit 1
  fi
  echo "==> flashing $label on $port"
  (
    cd "$build_dir"
    "$PYTHON" -m esptool --chip esp32s3 --port "$port" --baud 921600 \
      write_flash @flash_args
  )
}

echo "WARNING: confirm each port maps to the correct board role (TX / RX-A / RX-B)."
echo
flash_board "csi_tx"  "$TX_PORT"  "$ROOT/firmware/csi_tx/build"
flash_board "csi_rx-a" "$RX_A_PORT" "$ROOT/firmware/csi_rx/build"
flash_board "csi_rx-b" "$RX_B_PORT" "$ROOT/firmware/csi_rx/build"
echo
echo "All three boards flashed. Plug them into the room topology, then run:"
echo "  make dev MODE=live RX_PORTS=rx-a=$RX_A_PORT,rx-b=$RX_B_PORT"
