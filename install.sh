#!/bin/bash
# One-line installer for git-auto-sync (macOS + Linux).
#
#   curl -fsSL https://raw.githubusercontent.com/OctopusGarage/git-auto-sync/main/install.sh | bash
#
# Installs uv (if missing), downloads the latest release tarball to
# ~/.git-auto-sync (override with GIT_AUTO_SYNC_DIR), syncs deps, drops a global
# `git-auto-sync` launcher into ~/.local/bin, and runs the guided `init` wizard.
# Re-running it updates an existing install. Pin a version with
# GIT_AUTO_SYNC_VERSION=v0.1.0.
set -euo pipefail

REPO="OctopusGarage/git-auto-sync"
INSTALL_DIR="${GIT_AUTO_SYNC_DIR:-$HOME/.git-auto-sync}"
BIN_DIR="$HOME/.local/bin"
CONFIG_PATH="$HOME/.git-auto-sync/config.toml"
VERSION="${GIT_AUTO_SYNC_VERSION:-latest}"
ORIGINAL_PATH="$PATH"

info() { printf '\033[1;34m=>\033[0m %s\n' "$*"; }
err() { printf '\033[1;31mxx\033[0m %s\n' "$*" >&2; }

case "$(uname)" in
  Darwin | Linux) ;;
  *) err "git-auto-sync supports macOS and Linux only."; exit 1 ;;
esac

# 1. uv
if ! command -v uv >/dev/null 2>&1; then
  info "Installing uv..."
  curl -LsSf https://astral.sh/uv/install.sh | sh
  export PATH="$BIN_DIR:$PATH"
fi
command -v uv >/dev/null 2>&1 || {
  err "uv install failed - see https://docs.astral.sh/uv/"
  exit 1
}
UV_BIN="$(command -v uv)"

# 2. resolve the release tag (follow the /releases/latest redirect; no jq needed)
if [ "$VERSION" = "latest" ]; then
  url=$(curl -fsSLI -o /dev/null -w '%{url_effective}' \
    "https://github.com/$REPO/releases/latest") || {
    err "Couldn't reach GitHub to resolve the latest release."
    exit 1
  }
  TAG="${url##*/}"
else
  TAG="$VERSION"
fi
case "$TAG" in
  v*) ;;
  *) err "Couldn't resolve a release tag (got '$TAG')."; exit 1 ;;
esac

# 3. download + extract the release tarball into INSTALL_DIR.
#    config.toml/sync.log live here too but are absent from the archive, so an
#    update preserves them.
PACKAGE_FILE="git-auto-sync-${TAG}-release.tar.gz"
info "Downloading release package..."
tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT

if ! curl -fsSL --max-time 120 "https://github.com/$REPO/releases/download/$TAG/$PACKAGE_FILE" \
  -o "$tmp/release.tar.gz"; then
  info "Release package not found. Falling back to source archive..."
  if ! curl -fsSL --max-time 120 "https://github.com/$REPO/archive/refs/tags/${TAG}.tar.gz" \
    -o "$tmp/release.tar.gz"; then
    err "Download failed for $TAG."
    exit 1
  fi
fi
# Migrate a previous git-clone install: drop its VCS metadata, keep config/logs.
[ -d "$INSTALL_DIR/.git" ] && rm -rf "$INSTALL_DIR/.git"
mkdir -p "$INSTALL_DIR"
tar -xzf "$tmp/release.tar.gz" --strip-components=1 -C "$INSTALL_DIR"
cd "$INSTALL_DIR"

# 4. dependencies
info "Syncing dependencies..."
"$UV_BIN" sync

# 5. global launcher, so `git-auto-sync ...` works from anywhere
info "Installing launcher to $BIN_DIR/git-auto-sync..."
mkdir -p "$BIN_DIR"
cat >"$BIN_DIR/git-auto-sync" <<EOF
#!/bin/bash
export GIT_AUTO_SYNC_UV="$UV_BIN"
exec "$UV_BIN" run --project "$INSTALL_DIR" git-auto-sync "\$@"
EOF
chmod +x "$BIN_DIR/git-auto-sync"
case ":$PATH:" in
  *":$BIN_DIR:"*) ;;
  *) export PATH="$BIN_DIR:$PATH" ;;
esac

# 6. guided setup - read prompts from the terminal even when piped via curl.
#    When piped (no tty) we fall back to --yes, which writes a config but does
#    NOT install the scheduler (this tool auto-commits AND pushes; arming that
#    unattended needs an explicit `git-auto-sync install`).
if [ -e "$CONFIG_PATH" ]; then
  info "Existing config found at $CONFIG_PATH; skipping guided setup."
  info "Run 'git-auto-sync init' to reconfigure."
else
  info "Starting guided setup..."
  if [ -t 0 ]; then
    "$BIN_DIR/git-auto-sync" init
  elif { : </dev/tty; } 2>/dev/null; then
    "$BIN_DIR/git-auto-sync" init </dev/tty
  else
    "$BIN_DIR/git-auto-sync" init --yes
  fi
fi

info "Done. Installed $TAG at $INSTALL_DIR"
info "Update later with:  git-auto-sync update"
case ":$ORIGINAL_PATH:" in
  *":$BIN_DIR:"*) ;;
  *) info "Add $BIN_DIR to your PATH to use the 'git-auto-sync' command." ;;
esac
