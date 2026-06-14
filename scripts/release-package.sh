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

cp -f "$ROOT_DIR/README.md" "$PACKAGE_ROOT/INSTALL.md"

tar -czf "$DIST_DIR/${PACKAGE_NAME}.tar.gz" -C "$TMP_DIR" "$PACKAGE_NAME"
shasum -a 256 "$DIST_DIR/${PACKAGE_NAME}.tar.gz" | awk '{print $1}' > "$DIST_DIR/${PACKAGE_NAME}.tar.gz.sha256sum"

(
  cd "$TMP_DIR" && zip -r "$DIST_DIR/${PACKAGE_NAME}.zip" "$PACKAGE_NAME" >/dev/null
)
shasum -a 256 "$DIST_DIR/${PACKAGE_NAME}.zip" | awk '{print $1}' > "$DIST_DIR/${PACKAGE_NAME}.zip.sha256sum"

rm -rf "$TMP_DIR"

for artifact in "${ARTIFACTS[@]}"; do
  ls -lh "$artifact"
done

echo "Release artifacts generated:"
cat "$DIST_DIR/${PACKAGE_NAME}.tar.gz.sha256sum"
cat "$DIST_DIR/${PACKAGE_NAME}.zip.sha256sum"
