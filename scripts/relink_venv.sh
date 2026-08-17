#!/bin/sh
# Re-point the bundled venv at the bundled CPython runtime after unpacking on
# the colleague's machine. Run once after extracting the handoff bundle:
#
#   scripts/relink_venv.sh
#
# The tar preserves the venv's python symlink, but it points at the original
# packager's uv-managed interpreter (absolute path). This script rewrites the
# symlinks, pyvenv.cfg home, and console-script shebangs to the local path.
set -eu

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PYHOME="$ROOT/.handoff-python/bin"

if [ ! -x "$PYHOME/python3.11" ]; then
  echo "error: bundled runtime not found at $PYHOME" >&2
  echo "This bundle carries a self-contained CPython 3.11.15 (macOS arm64)." >&2
  exit 1
fi

ln -sfn "$PYHOME/python3.11" "$ROOT/.venv/bin/python"
ln -sfn python "$ROOT/.venv/bin/python3"
ln -sfn python "$ROOT/.venv/bin/python3.11"

sed -i '' "s|^home = .*|home = $PYHOME|" "$ROOT/.venv/pyvenv.cfg"

find "$ROOT/.venv/bin" -maxdepth 1 -type f -print0 2>/dev/null |
  while IFS= read -r -d '' f; do
    if head -1 "$f" 2>/dev/null | grep -q '^#!.*\.venv/bin/python'; then
      sed -i '' "s|^#!.*\.venv/bin/python|#!$ROOT/.venv/bin/python|" "$f"
    fi
  done

"$ROOT/.venv/bin/python" -c "import sys; print('python OK:', sys.version.split()[0])"
"$ROOT/.venv/bin/python" -m esptool version
echo "venv relinked: $ROOT/.venv/bin/python -> $PYHOME/python3.11"
