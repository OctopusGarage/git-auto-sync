# git-auto-sync

Monitor multiple local Git repositories on a schedule, automatically pick files to commit, generate a commit message, push changes, and notify via your chosen channels.

It is inspired by a single-repo bash script but redesigned for multi-repo workflows with a configuration-driven model, platform-native scheduling, and pluggable AI and notifier providers.

## Workflow

For each configured repository:

1. Skip with no output when there are no changes
2. **Smart staging**: let AI review changed files and select commit candidates, excluding secrets, build artifacts, and large files. Excluded files can be auto-added to `.gitignore` (if AI is unavailable, it falls back to `git add -A`).
3. AI generates a Conventional Commits message.
4. `git commit`
5. `git pull --rebase` → `git push` (on conflict, abort cleanly, mark as failed, continue with the next repo).
6. Summarize and notify by strategy.

## Installation

### One-line install (recommended)

macOS / Linux:

```bash
curl -fsSL https://raw.githubusercontent.com/OctopusGarage/git-auto-sync/main/install.sh | bash
```

Windows PowerShell:

```powershell
powershell -ExecutionPolicy ByPass -c "irm https://raw.githubusercontent.com/OctopusGarage/git-auto-sync/main/install.ps1 | iex"
```

It installs automatically: installs [uv](https://docs.astral.sh/uv/) when missing, downloads the latest release to `~/.git-auto-sync`, runs `uv sync`, and places a global `git-auto-sync` launcher in `~/.local/bin` (shell script on macOS/Linux, `.cmd` on Windows). The first run starts `init`. Re-running updates the existing installation; existing config is preserved by default. Use `GIT_AUTO_SYNC_VERSION=v0.1.0` for a pinned version and `GIT_AUTO_SYNC_DIR` to change install path.

> Non-interactive installs (`--yes`) write the config and skip scheduler setup, then run `init` so a repository does not become automatically scheduled until you explicitly run `git-auto-sync install`.

### Manual install

```bash
cd git-auto-sync
uv sync                       # Install dependencies
uv run git-auto-sync init     # Run the setup wizard (see below)
# Or install as a CLI command:
uv tool install .
```

### Setup wizard (`init`)

```bash
git-auto-sync init            # Interactive: scan directories, choose repos, pick AI provider, configure notifiers, and optionally install scheduler
git-auto-sync init --yes      # Non-interactive with defaults; scheduler is not installed
```

The wizard scans up to two levels deep from the parent directory (`~/programming` by default) and lets you pick repositories; you can also add paths manually. After writing `~/.git-auto-sync/config.toml`, it validates immediately.

### Update

```bash
git-auto-sync update          # Download latest release and run uv sync (launcher path remains stable, scheduler is not reinstalled)
git-auto-sync update --check  # Check for updates only
```

## Configuration

Default config path is `~/.git-auto-sync/config.toml` (override with `--config`). Runtime files (config, logs, scheduler artifacts) are stored in `~/.git-auto-sync/`.

```bash
mkdir -p ~/.git-auto-sync
cp config.example.toml ~/.git-auto-sync/config.toml
```

See [`config.example.toml`](config.example.toml) for all fields.

- `[defaults]` provides global defaults, and each `[[repos]]` can override fields.
- String values can use `env:VARNAME` and are resolved from environment variables at runtime.
- `ai_provider`: `claude-cli` (default, uses local `claude` CLI) / `anthropic-api` (reads `ANTHROPIC_API_KEY`) / `rules` (rule-based fallback). If any AI provider fails, the flow automatically falls back to rule mode.
- `notify_on`: `change_or_fail` (default, changed or failed only), `fail_only`, or `always`.

## Commands

```bash
git-auto-sync init                  # Run setup wizard and create config
git-auto-sync sync                  # Sync all repositories
git-auto-sync sync --repo foo       # Sync only repos matching path foo
git-auto-sync sync --dry-run        # Show candidates without changing anything
git-auto-sync status                # Show branches and clean/dirty state per repo
git-auto-sync config check          # Validate config file
git-auto-sync install --interval 30m  # Install platform-native scheduler
git-auto-sync uninstall             # Remove scheduler integration
git-auto-sync update                # Self-update to latest release
```

Exit codes: `0` = success, `1` = at least one repository failed, `2` = `--repo` matched no repository.

## Scheduling

`install` creates and enables a platform-native scheduler and does not run a resident process:

- **macOS** → launchd(`~/Library/LaunchAgents/com.octopusgarage.git-auto-sync.plist`)
- **Linux** → systemd user timer(`~/.config/systemd/user/git-auto-sync.timer`)
- **Windows** → Task Scheduler(`OctopusGarage.git-auto-sync`)

Intervals support `30m` / `1h` / `90s`. Uninstall with `git-auto-sync uninstall`.

## Notifiers

- `log`: append timestamped blocks to log file and print to stdout (audit friendly)
- `telegram`: bot token + chat_id
- `lark`: Feishu custom robot webhook

After each sync, a summary is sent through all enabled notifiers according to `notify_on`. Failure in one notifier does not affect others or the main sync flow.

## Safety boundaries

The biggest risk in unattended automation is committing bad content. This tool defends with:

- AI staging excludes secrets, credentials, certificates, `node_modules`/`dist`/`build`/`__pycache__`, large binaries, logs, and other non-source artifacts.
- Excluded files are **never committed** and are written into `.gitignore` when `ai_gitignore_autowrite=true`.
- When uncertain, run `--dry-run` first to preview.

## Development

```bash
uv run pytest          # Run tests
uv run ruff check .    # Run linting
```

## Release

Use the release runbook to keep every release consistent:

- `release.md` provides the canonical release procedure and naming standards.
- `.claude/commands/release.md` provides the runnable AI command flow.

Both paths are aligned and require this package output:

- `dist/git-auto-sync-vX.Y.Z-release.tar.gz`
- `dist/git-auto-sync-vX.Y.Z-release.zip`

Run either:

```bash
# macOS / Linux
cat release.md
cat .claude/commands/release.md

# Windows
Get-Content release.md
Get-Content .claude/commands/release.md
```

Use this copy-paste prompt for AI-assisted release operations:

```text
Run the full release flow in .claude/commands/release.md:
preflight, version bump, minimal package build, publish + asset upload,
and cross-platform validation.
Stop immediately on first failure and report the blocked step plus fix.
```

Copyable release note sample and AI install assistant prompt:

````markdown
## Changes

- feat+fix: release hardening and cross-platform install packaging

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

Prefer an AI assistant? Paste this to Claude Code / Codex / Gemini CLI (or a shell AI agent):

```text
Install "git-auto-sync" on my machine for me (open-source, cross-platform). Download the latest
release tarball from https://github.com/OctopusGarage/git-auto-sync/releases/latest, extract it, read the
INSTALL.md inside, and follow it. Guide me step by step and ask me for anything it needs
(like my Telegram bot token).
```

**Full Changelog**: https://github.com/OctopusGarage/git-auto-sync/compare/v0.1.6...v0.1.7
````

For manual release scripts, run the version bump and release flow in that file.

## License

MIT
