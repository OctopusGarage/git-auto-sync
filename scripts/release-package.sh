#!/usr/bin/env bash

set -euo pipefail

if [[ $# -ne 1 ]]; then
  echo "Usage: scripts/release-package.sh <version>"
  echo "Example: scripts/release-package.sh v0.1.0"
  exit 1
fi

VERSION="$1"
if [[ "$VERSION" != v* ]]; then
  VERSION="v${VERSION}"
fi

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DIST_DIR="$ROOT_DIR/dist"
TMP_DIR="$(mktemp -d)"
PACKAGE_NAME="git-auto-sync-${VERSION}-release"
PACKAGE_ROOT="$TMP_DIR/$PACKAGE_NAME"
PYTHON_BIN="${PYTHON:-}"
ARTIFACTS=(
  "$DIST_DIR/${PACKAGE_NAME}.tar.gz"
  "$DIST_DIR/${PACKAGE_NAME}.tar.gz.sha256sum"
  "$DIST_DIR/${PACKAGE_NAME}.zip"
  "$DIST_DIR/${PACKAGE_NAME}.zip.sha256sum"
)

RELEASE_FILES=(
  "git_auto_sync"
  "README.md"
  "config.example.toml"
  "install.sh"
  "install.ps1"
  "pyproject.toml"
  "uv.lock"
)

if [[ -z "$PYTHON_BIN" ]]; then
  if command -v python3 >/dev/null 2>&1; then
    PYTHON_BIN="python3"
  elif command -v python >/dev/null 2>&1; then
    PYTHON_BIN="python"
  else
    echo "Missing required command for release package: python3 or python" >&2
    exit 1
  fi
fi

for item in "${RELEASE_FILES[@]}"; do
  if [[ ! -e "$ROOT_DIR/$item" ]]; then
    echo "Missing required file for release package: $item" >&2
    exit 1
  fi
done

rm -rf "$DIST_DIR"
mkdir -p "$DIST_DIR"
mkdir -p "$PACKAGE_ROOT"

for item in "${RELEASE_FILES[@]}"; do
  cp -R "$ROOT_DIR/$item" "$PACKAGE_ROOT/"
done

find "$PACKAGE_ROOT" -type d -name "__pycache__" -prune -exec rm -rf {} +
find "$PACKAGE_ROOT" -type f \( -name "*.pyc" -o -name "*.pyo" \) -delete

cp -f "$ROOT_DIR/README.md" "$PACKAGE_ROOT/INSTALL.md"

tar -czf "$DIST_DIR/${PACKAGE_NAME}.tar.gz" -C "$TMP_DIR" "$PACKAGE_NAME"
(
  cd "$DIST_DIR"
  "$PYTHON_BIN" - "${PACKAGE_NAME}.tar.gz" "${PACKAGE_NAME}.tar.gz.sha256sum" <<'PY'
from pathlib import Path
import hashlib
import sys

archive = Path(sys.argv[1])
checksum = Path(sys.argv[2])
checksum.write_text(hashlib.sha256(archive.read_bytes()).hexdigest() + "\n", encoding="utf-8")
PY
)

(
  cd "$TMP_DIR"
  "$PYTHON_BIN" - "$PACKAGE_NAME" "${PACKAGE_NAME}.zip" <<'PY'
from pathlib import Path
import sys
import zipfile

package_name = sys.argv[1]
archive = Path(sys.argv[2])
package_root = Path(package_name)

with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as zf:
    for path in sorted(package_root.rglob("*")):
        if path.is_file():
            zf.write(path, path.as_posix())
PY
  cp -f "${PACKAGE_NAME}.zip" "$DIST_DIR/${PACKAGE_NAME}.zip"
)

(
  cd "$DIST_DIR"
  "$PYTHON_BIN" - "${PACKAGE_NAME}.zip" "${PACKAGE_NAME}.zip.sha256sum" <<'PY'
from pathlib import Path
import hashlib
import sys

archive = Path(sys.argv[1])
checksum = Path(sys.argv[2])
checksum.write_text(hashlib.sha256(archive.read_bytes()).hexdigest() + "\n", encoding="utf-8")
PY
)

rm -rf "$TMP_DIR"

for artifact in "${ARTIFACTS[@]}"; do
  ls -lh "$artifact"
done

echo "Release artifacts generated:"
cat "$DIST_DIR/${PACKAGE_NAME}.tar.gz.sha256sum"
cat "$DIST_DIR/${PACKAGE_NAME}.zip.sha256sum"
