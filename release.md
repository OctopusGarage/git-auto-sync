# Release Standard (Git Auto Sync)

This repository uses one release format for every publish so installation and CI validation stay consistent.

## Required release artifacts

Every release must include four assets:

- `git-auto-sync-vX.Y.Z-release.tar.gz`
- `git-auto-sync-vX.Y.Z-release.tar.gz.sha256sum`
- `git-auto-sync-vX.Y.Z-release.zip`
- `git-auto-sync-vX.Y.Z-release.zip.sha256sum`

## Required package contents

The installable package must contain only runtime files:

- `git_auto_sync/`
- `README.md`
- `INSTALL.md` (copied from `README.md`)
- `config.example.toml`
- `install.sh`
- `install.ps1`
- `pyproject.toml`
- `uv.lock`

Do not include:

- `.github/`
- `.claude/`
- `tests/`
- cache directories
- project metadata directories (like `.git/`, `.venv/`, `__pycache__`, etc.)

## Mandatory release commands (run on `main`)

```bash
# 1) Clean workspace and preflight
git checkout main
git pull --ff-only origin main
git status --short
uv run pytest -q
uv run ruff check .
uv run ruff format --check git_auto_sync/ tests/
```

```bash
# 2) Bump version (patch/minor/major or explicit X.Y.Z)
# Use release tooling or bump files as your preferred method in the repository.
```

```bash
# 3) Build release assets (fixed list, all platforms)
scripts/release-package.sh vX.Y.Z
```

```bash
# 4) Create release and upload both assets
cat /tmp/release-notes.md  # prepare notes first
gh release create vX.Y.Z --title "git-auto-sync vX.Y.Z" --notes-file /tmp/release-notes.md
gh release upload vX.Y.Z dist/git-auto-sync-vX.Y.Z-release.tar.gz dist/git-auto-sync-vX.Y.Z-release.tar.gz.sha256sum dist/git-auto-sync-vX.Y.Z-release.zip dist/git-auto-sync-vX.Y.Z-release.zip.sha256sum --clobber
```

```bash
# 5) Validate CI is green and keep fixing until it passes
gh run list --workflow ci.yml --limit 1 --json databaseId --jq '.[0].databaseId' | xargs -I{} gh run watch {}
```

```bash
# 6) Validate installation/update on all platforms
curl -fsSL https://raw.githubusercontent.com/OctopusGarage/git-auto-sync/main/install.sh | bash
git-auto-sync --help

# Windows
powershell -ExecutionPolicy ByPass -c "irm https://raw.githubusercontent.com/OctopusGarage/git-auto-sync/main/install.ps1 | iex"
git-auto-sync --help
```

## Release note template (copy/paste)

```markdown
## Changes

- feat+fix: release hardening and full-platform packaging consistency

## Install / update

### macOS / Linux

```bash
curl -fsSL https://raw.githubusercontent.com/OctopusGarage/git-auto-sync/main/install.sh | bash
```

### Windows

```powershell
powershell -ExecutionPolicy ByPass -c "irm https://raw.githubusercontent.com/OctopusGarage/git-auto-sync/main/install.ps1 | iex"
```

Pin this version with `GIT_AUTO_SYNC_VERSION=vX.Y.Z`. See README.md for dev, deploy, and release.

Prefer an AI assistant? Paste this to Claude Code / Codex / Gemini CLI / shell AI agent:

```text
Install "git-auto-sync" on my machine for me (open-source, cross-platform).
Download the latest release assets from
https://github.com/OctopusGarage/git-auto-sync/releases/latest, verify checksums if provided,
extract the install package, read INSTALL.md inside, and follow it.
Guide me step by step and ask me for anything it needs (like my Telegram bot token).
```

**Full Changelog**: https://github.com/OctopusGarage/git-auto-sync/compare/v0.1.0...vX.Y.Z
```

## Mandatory consistency checks

- Tar.gz and zip assets exist and are uploaded together.
- SHA-256 files exist for both assets.
- Package contains only approved files above.
- CI for this tag reaches `success` before announcing release.
