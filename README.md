# git-auto-sync

Automatically commit, rebase, push, and notify across many local Git repositories.

[![CI](https://github.com/OctopusGarage/git-auto-sync/actions/workflows/ci.yml/badge.svg)](https://github.com/OctopusGarage/git-auto-sync/actions/workflows/ci.yml)
[![Python](https://img.shields.io/badge/Python-3.11%2B-3776ab?logo=python&logoColor=white)](pyproject.toml)
[![Version](https://img.shields.io/badge/version-0.2.0-blue)](pyproject.toml)
[![License](https://img.shields.io/badge/license-MIT-yellow)](pyproject.toml)

## Why

Personal machines often hold many small active repositories. `git-auto-sync` keeps them clean without turning `git add -A && git commit && git push` into a risky cron job. It can ask an AI provider to stage only reasonable files, generate a Conventional Commits message, push safely, and notify when something changed or failed.

## Features

- **Multi-repo scheduler** - scan and sync configured repositories on macOS, Linux, or Windows.
- **Smart staging** - AI selects commit candidates and excludes secrets, build output, logs, binaries, and large files.
- **Path policies** - allowlist or exclude paths with gitignore-style patterns before staging.
- **Bare work tree support** - sync `git_dir` plus `work_tree` repositories, including config repos outside a normal `.git` directory.
- **Safe fallback** - when AI is unavailable, rule-based staging still keeps common junk out.
- **Conventional commits** - generate commit messages from the selected diff.
- **Conflict isolation** - failed pull/rebase in one repo does not stop the rest.
- **Pluggable notifications** - log, Telegram, and Feishu/Lark webhook notifiers.
- **Dry-run mode** - preview candidates without committing or pushing.
- **One-line install** - installer sets up `uv`, release files, config, and command launcher.

## Quick Start

macOS / Linux:

```bash
curl -fsSL https://raw.githubusercontent.com/OctopusGarage/git-auto-sync/main/install.sh | bash
```

Windows PowerShell:

```powershell
powershell -ExecutionPolicy ByPass -c "irm https://raw.githubusercontent.com/OctopusGarage/git-auto-sync/main/install.ps1 | iex"
```

Then run the guided setup:

```bash
git-auto-sync init
git-auto-sync sync --dry-run
git-auto-sync sync
```

## Workflow

For each configured repository:

1. Skip clean repositories.
2. Select safe files to stage.
3. Generate a Conventional Commits message.
4. Commit.
5. Pull with rebase.
6. Push.
7. Notify according to the configured strategy.

If any step fails, that repository is marked failed and the next repository continues.

## Commands

```bash
git-auto-sync init
git-auto-sync status
git-auto-sync sync
git-auto-sync sync --repo my-project
git-auto-sync sync --dry-run
git-auto-sync config check
git-auto-sync install --interval 30m
git-auto-sync uninstall
git-auto-sync update
```

## Configuration

Default config path:

```text
~/.git-auto-sync/config.toml
```

Start from the example:

```bash
mkdir -p ~/.git-auto-sync
cp config.example.toml ~/.git-auto-sync/config.toml
git-auto-sync config check
```

Core options:

| Setting | Purpose |
|---|---|
| `[[repos]]` | Repositories to scan and sync. |
| `ai_provider` | `claude-cli`, `anthropic-api`, or `rules`. |
| `notify_on` | `change_or_fail`, `fail_only`, or `always`. |
| notifiers | `log`, `telegram`, and `lark`. |

Path policies are optional for normal repositories:

```toml
[[repos]]
path = "~/programming/docs"

[repos.path_policy]
mode = "allowlist"
include = ["README.md", "docs/**"]
exclude = ["*.log", ".env*"]
builtin_deny = true
```

`git_dir` plus `work_tree` repositories are also supported. This mode always
requires `path_policy.mode = "allowlist"` with `include` or `include_file`:

```toml
[[repos]]
name = "home-config"
path = "~"
git_dir = "~/.homegit.git"
work_tree = "~"
ai_staging = false

[repos.path_policy]
mode = "allowlist"
include_file = "~/.homegitinclude"
exclude_file = "~/.homegitignore"
builtin_deny = true
```

If the effective work tree is the user's home directory, the same allowlist
requirement is enforced even when `git_dir` is not configured.

## Scheduler

`git-auto-sync install` creates a platform-native schedule:

| Platform | Mechanism |
|---|---|
| macOS | `launchd` user agent |
| Linux | `systemd --user` timer |
| Windows | Task Scheduler |

No long-running daemon is required.

## Safety Boundaries

- Secret-like files, certificates, build artifacts, dependency folders, logs, and large binaries are excluded from staging.
- When a path policy is configured, AI staging can only choose from files already approved by that policy.
- `git_dir` plus `work_tree` repositories and home-directory work trees must use an allowlist policy.
- Excluded paths can be written to `.gitignore` when `ai_gitignore_autowrite=true`.
- `--dry-run` shows what would happen before any commit or push.
- Pull conflicts abort cleanly and do not continue into a risky push.

## Development

```bash
uv sync
uv run pytest
uv run ruff check .
```

## Release

See [release.md](release.md) for the release runbook and package asset rules.

## Related

- [tmux-claude-bot](https://github.com/OctopusGarage/tmux-claude-bot) - remote-control local coding agents in tmux.
- [OctopusGarage](https://github.com/OctopusGarage) - small tools for AI agents, local automation, and browser-native products.

## License

MIT
