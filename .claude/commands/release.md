description: Cut a production-ready release with strict cross-platform package consistency
argument-hint: "[patch|minor|major|X.Y.Z]"
allowed-tools: Bash, PowerShell, Read, Edit, Write
---

You are running the **git-auto-sync release runbook**. Execute these phases exactly in order.
Treat every failing check as a hard stop and fix before continuing.

Arguments: `$ARGUMENTS`
- `patch` (default), `minor`, `major`, or explicit `X.Y.Z`.

## 0) Baseline and preflight

```bash
git remote -v
git branch --show-current
git status --short
git fetch --all --prune --tags
git pull --ff-only origin main
```

```bash
command -v gh >/dev/null || { echo "Install gh first"; exit 1; }
command -v uv >/dev/null || { echo "Install uv first"; exit 1; }
command -v tar >/dev/null || { echo "Install tar first"; exit 1; }
command -v zip >/dev/null || { echo "Install zip first"; exit 1; }
```

```bash
uv run pytest -q
uv run ruff check .
uv run ruff format --check git_auto_sync/ tests/
```

## 1) Decide version

```bash
CURRENT="$(grep -m1 '^version' pyproject.toml | sed 's/version *= *\"//;s/\"//')"
BASE="v${CURRENT}"
echo "Current version: $BASE"
```

```bash
if [ "$ARGUMENTS" = "patch" ] || [ "$ARGUMENTS" = "" ]; then
  VERSION="v$(python - <<'PY'
from pathlib import Path
ver = Path('pyproject.toml').read_text().split('version = \"',1)[1].split('\"',1)[0]
major, minor, patch = map(int, ver.split('.'))
print(f"{major}.{minor}.{patch+1}")
PY
  )"
elif [ "$ARGUMENTS" = "minor" ]; then
  VERSION="v$(python - <<'PY'
from pathlib import Path
ver = Path('pyproject.toml').read_text().split('version = \"',1)[1].split('\"',1)[0]
major, minor, patch = map(int, ver.split('.'))
print(f"{major}.{minor+1}.0")
PY
  )"
elif [ "$ARGUMENTS" = "major" ]; then
  VERSION="v$(python - <<'PY'
from pathlib import Path
ver = Path('pyproject.toml').read_text().split('version = \"',1)[1].split('\"',1)[0]
major, minor, patch = map(int, ver.split('.'))
print(f"{major+1}.0.0")
PY
  )"
else
  VERSION="$ARGUMENTS"
  [[ "$VERSION" == v* ]] || VERSION="v${VERSION}"
fi
echo "Release version: $VERSION"
```

## 2) Bump version files

```bash
sed -i "s/^version = \".*\"/version = \"${VERSION#v}\"/" pyproject.toml
sed -i "s/^__version__ = \".*\"/__version__ = \"${VERSION#v}\"/" git_auto_sync/__init__.py
uv sync
git add pyproject.toml git_auto_sync/__init__.py uv.lock
git commit -m "chore: bump version to ${VERSION}"
```

## 3) Build release package from fixed file list (tar.gz + zip)

```bash
scripts/release-package.sh "${VERSION}"
ls -lh dist
```

## 4) Prepare release notes (must match policy)

```bash
PREV_TAG="$(git describe --tags --abbrev=0 HEAD^ 2>/dev/null || true)"
if [ -z "${PREV_TAG}" ]; then PREV_TAG="$(git rev-list --max-parents=0 HEAD)"; fi
cat > /tmp/release-notes.md <<'EOF'
## Changes

- feat+fix: release hardening and full-platform packaging consistency (post-${VERSION})

## Install / update

### macOS / Linux

```bash
curl -fsSL https://raw.githubusercontent.com/OctopusGarage/git-auto-sync/main/install.sh | bash
```

### Windows

```powershell
powershell -ExecutionPolicy ByPass -c "irm https://raw.githubusercontent.com/OctopusGarage/git-auto-sync/main/install.ps1 | iex"
```

Pin this version with `GIT_AUTO_SYNC_VERSION=${VERSION}`. See README.md for dev, deploy, and release.

Prefer an AI assistant? Paste this to Claude Code / Codex / Gemini CLI / shell AI agent:

```text
Install "git-auto-sync" on my machine for me (open-source, cross-platform). Download the latest
release assets from https://github.com/OctopusGarage/git-auto-sync/releases/latest, verify checksums,
extract the install package, read INSTALL.md inside, and follow it. Ask me for anything needed
(like my Telegram bot token).
```

**Full Changelog**: https://github.com/OctopusGarage/git-auto-sync/compare/${PREV_TAG}...${VERSION}
EOF
cat /tmp/release-notes.md
```

## 5) Create or replace release and upload both asset formats

```bash
gh release delete "${VERSION}" --yes || true
gh release create "${VERSION}" --target main --title "git-auto-sync ${VERSION}" --notes-file /tmp/release-notes.md
gh release upload "${VERSION}" dist/git-auto-sync-${VERSION}-release.tar.gz \
  dist/git-auto-sync-${VERSION}-release.tar.gz.sha256sum \
  dist/git-auto-sync-${VERSION}-release.zip \
  dist/git-auto-sync-${VERSION}-release.zip.sha256sum \
  --clobber
```

## 6) Push branch and tag

```bash
git push --follow-tags origin main
```

## 7) Monitor CI for this tag and keep fixing until green

```bash
RUN_ID="$(gh run list --workflow ci.yml --limit 1 --json databaseId --jq '.[0].databaseId')"
gh run view "$RUN_ID" --json status,conclusion,workflowName,name,url -q '{workflow: .workflowName, name: .name, status: .status, conclusion: .conclusion, url: .url}'
gh run watch "$RUN_ID"
```

## 8) Validate install/update on all platforms

```bash
curl -fsSL https://raw.githubusercontent.com/OctopusGarage/git-auto-sync/main/install.sh | bash
git-auto-sync --help
git-auto-sync --version
git-auto-sync update --check
```

```powershell
powershell -ExecutionPolicy ByPass -c "irm https://raw.githubusercontent.com/OctopusGarage/git-auto-sync/main/install.ps1 | iex"
git-auto-sync --help
git-auto-sync --version
git-auto-sync update --check
```

## AI operator summary command (copy/paste)

```text
You are a strict release operator for the git-auto-sync repository.
Run the `.claude/commands/release.md` flow exactly with argument: `$ARGUMENTS`.
Every required step must complete:
1) preflight checks
2) version decision + bumps
3) release-package script
4) release notes + GitHub release
5) CI monitoring until success
6) macOS/Linux + Windows install/update check
Stop at the first failure and report the exact failed command and required fix.
```

## Completion report

```bash
echo "VERSION=${VERSION}"
gh release view "${VERSION}" --json name,tagName,isLatest,publishedAt,url -q '{name, tag: .tagName, latest: .isLatest, publishedAt, url}'
gh release view "${VERSION}" --json assets --jq '.assets[].name'
```
