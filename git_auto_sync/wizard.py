"""Interactive setup wizard for git-auto-sync."""
from __future__ import annotations

import shutil
import sys
from pathlib import Path

from git_auto_sync.config import DEFAULT_CONFIG_PATH, load_config

# ---------------------------------------------------------------------------
# Pure helpers
# ---------------------------------------------------------------------------

def scan_git_repos(parent: str | Path) -> list[str]:
    """Return absolute paths of git repos found up to depth 2 under *parent*.

    Scanning rules (mirrors the common ``~/programming/<org>/<repo>`` layout):
    - For each immediate child of *parent*:
      - If the child itself is a git repo (has ``.git``), include it.
      - Otherwise descend ONE more level into the child and include any of
        its children that are git repos.
    - Never descend into a directory that is already a git repo.
    - Non-existent *parent* → ``[]``.

    Returns absolute, sorted, deduplicated paths.
    """
    parent = Path(parent)
    if not parent.exists():
        return []
    results: set[str] = set()
    for child in parent.iterdir():
        if not child.is_dir():
            continue
        if (child / ".git").exists():
            results.add(str(child.resolve()))
        else:
            # Descend one more level (depth 2)
            for grandchild in child.iterdir():
                if grandchild.is_dir() and (grandchild / ".git").exists():
                    results.add(str(grandchild.resolve()))
    return sorted(results)


def _toml_string(value: str) -> str:
    """Escape a TOML basic string value."""
    return value.replace("\\", "\\\\").replace('"', '\\"')


def render_config_toml(
    repos: list[str],
    ai_provider: str,
    notify_on: str,
    log_path: str,
    telegram: dict | None = None,
    lark: dict | None = None,
) -> str:
    """Return a complete, valid config.toml string.

    Always writes:
      - [defaults] with ai_provider, ai_staging=true, ai_gitignore_autowrite=true,
        push=true, notify_on
      - one [[repos]] per path
      - [notifiers.log] enabled=true with the given path

    If *telegram* dict given → enabled=true with bot_token/chat_id;
    else enabled=false with placeholder.

    Same pattern for *lark* (webhook key; placeholder URL when None).
    """
    lines: list[str] = []

    # [defaults]
    lines.append("[defaults]")
    lines.append(f'ai_provider = "{ai_provider}"')
    lines.append("ai_staging = true")
    lines.append("ai_gitignore_autowrite = true")
    lines.append("push = true")
    lines.append(f'notify_on = "{notify_on}"')
    lines.append("")

    # [[repos]]
    for path in repos:
        lines.append("[[repos]]")
        lines.append(f'path = "{_toml_string(path)}"')
        lines.append("")

    # [notifiers.log]
    lines.append("[notifiers.log]")
    lines.append("enabled = true")
    lines.append(f'path = "{_toml_string(log_path)}"')
    lines.append("")

    # [notifiers.telegram]
    lines.append("[notifiers.telegram]")
    if telegram:
        lines.append("enabled = true")
        lines.append(f'bot_token = "{_toml_string(telegram["bot_token"])}"')
        lines.append(f'chat_id = "{_toml_string(telegram["chat_id"])}"')
    else:
        lines.append("enabled = false")
        lines.append('bot_token = "env:TELEGRAM_BOT_TOKEN"')
        lines.append('chat_id = ""')
    lines.append("")

    # [notifiers.lark]
    lines.append("[notifiers.lark]")
    if lark:
        lines.append("enabled = true")
        lines.append(f'webhook = "{_toml_string(lark["webhook"])}"')
    else:
        lines.append("enabled = false")
        lines.append(
            'webhook = "https://open.larksuite.com/open-apis/bot/v2/hook/PLACEHOLDER"'
        )
    lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Interactive helpers
# ---------------------------------------------------------------------------

def _confirm(prompt: str, default: bool = True) -> bool:
    suffix = "[Y/n]" if default else "[y/N]"
    ans = input(f"{prompt} {suffix} ").strip().lower()
    if not ans:
        return default
    return ans in ("y", "yes")


# ---------------------------------------------------------------------------
# Main wizard flow
# ---------------------------------------------------------------------------

def run_init(args) -> int:
    """Interactive (or --yes) setup wizard.

    args must have:
      .config       – path override or None
      .yes          – bool
      .no_schedule  – bool
    """
    yes: bool = getattr(args, "yes", False)
    no_schedule: bool = getattr(args, "no_schedule", False)

    # ------------------------------------------------------------------ 1. Config path
    config_path = Path(args.config) if args.config else DEFAULT_CONFIG_PATH
    config_path = config_path.expanduser().resolve()
    config_path.parent.mkdir(parents=True, exist_ok=True)

    if config_path.exists():
        backup = Path(str(config_path) + ".bak")
        shutil.copy2(config_path, backup)
        print(f"• Backed up existing config → {backup}")

    # ------------------------------------------------------------------ 2. Repos
    default_parent = Path.home() / "programming"
    if not default_parent.exists():
        default_parent = Path.cwd()

    if yes:
        scan_parent = default_parent
    else:
        ans = input(f"  Parent directory to scan for git repos [{default_parent}]: ").strip()
        scan_parent = Path(ans).expanduser() if ans else default_parent

    found = scan_git_repos(scan_parent)

    selected: list[str] = []
    if found:
        print(f"  Found {len(found)} git repo(s) in {scan_parent}:")
        for i, p in enumerate(found):
            print(f"    [{i}] {p}")

        if yes:
            selected = list(found)
        else:
            ans = input(
                "  Select repos (comma-separated indexes, or Enter for all): "
            ).strip()
            if not ans:
                selected = list(found)
            else:
                chosen: list[str] = []
                for tok in ans.split(","):
                    tok = tok.strip()
                    try:
                        idx = int(tok)
                        if 0 <= idx < len(found):
                            chosen.append(found[idx])
                        else:
                            print(f"  ⚠ index {idx} out of range — skipped")
                    except ValueError:
                        # treat as path fragment / name
                        matches = [p for p in found if tok in p]
                        if matches:
                            chosen.extend(matches)
                        else:
                            print(f"  ⚠ no repo matching {tok!r} — skipped")
                selected = chosen
    else:
        print(f"  No git repos found under {scan_parent}.")

    if not yes:
        print("  Add extra absolute paths (one per line, blank to finish):")
        while True:
            extra = input("    > ").strip()
            if not extra:
                break
            selected.append(extra)

    if not selected:
        print("  ℹ No repos selected — you can add [[repos]] to the config later.")

    # ------------------------------------------------------------------ 3. AI provider
    has_claude = bool(shutil.which("claude"))
    default_provider = "claude-cli" if has_claude else "rules"
    providers = ["claude-cli", "anthropic-api", "rules"]

    if yes:
        ai_provider = default_provider
    else:
        print(f"  AI provider options: {', '.join(providers)}")
        if has_claude:
            print("  ✓ claude detected on PATH")
        else:
            print("  ⚠ claude not found on PATH")
        ans = input(f"  Choose AI provider [{default_provider}]: ").strip()
        ai_provider = ans if ans in providers else default_provider

    print(f"  ✓ ai_provider = {ai_provider}")

    # ------------------------------------------------------------------ 4. notify_on
    default_notify = "change_or_fail"
    if yes:
        notify_on = default_notify
    else:
        opts = "change_or_fail / fail_only / always"
        ans = input(f"  notify_on ({opts}) [{default_notify}]: ").strip()
        notify_on = ans if ans in {"change_or_fail", "fail_only", "always"} else default_notify
    print(f"  ✓ notify_on = {notify_on}")

    # ------------------------------------------------------------------ 5. Log path
    default_log = str(Path.home() / ".git-auto-sync" / "sync.log")
    if yes:
        log_path = default_log
    else:
        ans = input(f"  Log file path [{default_log}]: ").strip()
        log_path = ans if ans else default_log
    print(f"  ✓ log_path = {log_path}")

    # ------------------------------------------------------------------ 6. Telegram / Lark
    telegram: dict | None = None
    lark: dict | None = None

    if not yes:
        if _confirm("  Enable Telegram notifier?", default=False):
            default_token = "env:TELEGRAM_BOT_TOKEN"
            bot_token = input(f"    bot_token [{default_token}]: ").strip() or default_token
            chat_id = input("    chat_id: ").strip()
            telegram = {"bot_token": bot_token, "chat_id": chat_id}

        if _confirm("  Enable Lark (Feishu) notifier?", default=False):
            webhook = input("    webhook URL: ").strip()
            lark = {"webhook": webhook}

    # ------------------------------------------------------------------ 7. Write + validate
    # load_config requires at least one [[repos]].  When nothing was selected, write a
    # placeholder so the file is structurally valid; the user must replace it later.
    placeholder_used = False
    if not selected:
        placeholder_used = True
        repos_to_write = [str(Path.home() / "replace-me" / "your-repo")]
    else:
        repos_to_write = selected

    toml_str = render_config_toml(
        repos=repos_to_write,
        ai_provider=ai_provider,
        notify_on=notify_on,
        log_path=log_path,
        telegram=telegram,
        lark=lark,
    )
    config_path.write_text(toml_str, encoding="utf-8")
    print(f"\n✓ Wrote {config_path}")

    try:
        load_config(config_path)
        if placeholder_used:
            print("✓ Config valid (placeholder repo written — edit before running sync)")
        else:
            print("✓ Config valid")
    except Exception as exc:
        print(f"✗ Config validation failed: {exc}", file=sys.stderr)
        return 1

    # ------------------------------------------------------------------ 8. Scheduler
    if yes or no_schedule:
        print("\n  To install the scheduler later, run:")
        print("    git-auto-sync install --interval 30m")
    else:
        if _confirm("\n  Install the native scheduler now?", default=True):
            default_interval = "30m"
            interval = input(f"    Interval [{default_interval}]: ").strip() or default_interval
            try:
                from git_auto_sync.scheduler import install
                result = install(interval)
                print(f"  ✓ {result}")
            except Exception as exc:
                print(f"  ✗ Scheduler install failed: {exc}", file=sys.stderr)
        else:
            print("  To install the scheduler later, run:")
            print("    git-auto-sync install --interval 30m")

    # ------------------------------------------------------------------ 9. Closing checklist
    print("\nNext steps:")
    print(f"  • Edit {config_path} to add/adjust [[repos]]")
    print("  • Dry-run: git-auto-sync sync --dry-run")
    print("  • Check config: git-auto-sync config check")
    print("\n✓ Done.")
    return 0
