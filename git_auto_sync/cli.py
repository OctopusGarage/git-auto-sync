from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys

from git_auto_sync import __version__
from git_auto_sync.config import ConfigError, load_config
from git_auto_sync.engine import run_sync, should_notify
from git_auto_sync.notifiers import build_notifiers, format_summary
from git_auto_sync.providers import build_provider


def _cmd_sync(args) -> int:
    cfg = load_config(args.config)
    repos = cfg.repos
    if args.repo:
        repos = [
            r
            for r in repos
            if r.name == args.repo or r.path.endswith(args.repo) or args.repo in r.path
        ]
        if not repos:
            print(f"no repo matching: {args.repo}", file=sys.stderr)
            return 2
    summary = run_sync(repos, build_provider, dry_run=args.dry_run)

    policy = repos[0].notify_on if repos else "change_or_fail"
    if should_notify(policy, summary):
        text = format_summary(summary)
        for notifier in build_notifiers(cfg.notifiers):
            try:
                notifier.send(text)
            except Exception as exc:  # one notifier failing must not break others
                print(f"notifier error: {exc}", file=sys.stderr)
    return 1 if summary.failed else 0


def _cmd_status(args) -> int:
    from git_auto_sync.path_policy import status_pathspecs
    from git_auto_sync.repo_runtime import build_repo_runtime

    cfg = load_config(args.config)
    for r in cfg.repos:
        runtime = build_repo_runtime(r)
        pathspecs = status_pathspecs(r.path_policy)
        branch = runtime.current_branch()
        dirty = "dirty" if runtime.has_changes(pathspecs) else "clean"
        print(f"{r.path}  [{branch}]  {dirty}")
    return 0


def _cmd_install(args) -> int:
    from git_auto_sync.scheduler import install

    print(install(args.interval))
    return 0


def _cmd_uninstall(args) -> int:
    from git_auto_sync.scheduler import uninstall

    print(uninstall())
    return 0


def _cmd_config_check(args) -> int:
    try:
        cfg = load_config(args.config)
    except ConfigError as exc:
        print(f"config error: {exc}", file=sys.stderr)
        return 1
    print(f"OK: {len(cfg.repos)} repos, notifiers: {list(cfg.notifiers)}")
    return 0


def _cmd_init(args) -> int:
    from git_auto_sync.wizard import run_init

    return run_init(args)


def _uv_binary() -> str:
    return os.environ.get("GIT_AUTO_SYNC_UV") or shutil.which("uv") or "uv"


def _cmd_update(args) -> int:
    from git_auto_sync import release

    target = args.version or release.resolve_latest_tag()
    if not target:
        print("error: couldn't determine the latest release (network issue?)", file=sys.stderr)
        return 1

    installed = release.installed_version()

    if args.check:
        print(f"installed : {installed or 'unknown'}")
        print(f"available : {target}")
        if installed and release.is_newer(target, installed):
            print("update available")
        else:
            print("up to date")
        return 0

    if (
        not args.force
        and not args.version
        and installed
        and not release.is_newer(target, installed)
    ):
        print(f"already up to date ({installed})")
        return 0

    # Safety guard: refuse to overwrite a dev checkout without --force.
    if (release.PROJECT_DIR / ".git").exists():
        print(
            "warning: this looks like a git checkout "
            f"({release.PROJECT_DIR / '.git'}).\n"
            "The update command overwrites files in-place.  "
            "Use `git pull` instead, or pass --force to override.",
            file=sys.stderr,
        )
        if not args.force:
            return 1

    print(f"downloading {target}...")
    if not release.download_release(target, release.PROJECT_DIR):
        print("download/extract failed — install unchanged", file=sys.stderr)
        return 1

    print("syncing dependencies...")
    synced = subprocess.run([_uv_binary(), "sync"], cwd=release.PROJECT_DIR, check=False)
    if synced.returncode != 0:
        print(
            f"warning: code updated to {target} but `uv sync` failed "
            "— run `uv sync` manually to finish the update.",
            file=sys.stderr,
        )
        return 1

    print(f"updated to {target}.")
    print(
        "note: any installed scheduler keeps working automatically "
        "because it calls the stable launcher — no re-register needed."
    )
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="git-auto-sync")
    parser.add_argument(
        "--version",
        action="version",
        version=f"git-auto-sync {__version__}",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_init = sub.add_parser("init", help="interactive setup wizard")
    p_init.add_argument("--config", default=None, help="output config path")
    p_init.add_argument("-y", "--yes", action="store_true", help="accept defaults, no prompts")
    p_init.add_argument("--no-schedule", action="store_true", help="skip scheduler install step")
    p_init.set_defaults(func=_cmd_init)

    p_sync = sub.add_parser("sync", help="sync all or one repo")
    p_sync.add_argument("--config", default=None)
    p_sync.add_argument("--repo", default=None)
    p_sync.add_argument("--dry-run", action="store_true")
    p_sync.set_defaults(func=_cmd_sync)

    p_status = sub.add_parser("status", help="show repo states")
    p_status.add_argument("--config", default=None)
    p_status.set_defaults(func=_cmd_status)

    p_install = sub.add_parser("install", help="install native scheduler")
    p_install.add_argument("--interval", default="30m")
    p_install.set_defaults(func=_cmd_install)

    p_uninstall = sub.add_parser("uninstall", help="remove native scheduler")
    p_uninstall.set_defaults(func=_cmd_uninstall)

    p_update = sub.add_parser("update", help="update git-auto-sync to the latest release")
    p_update.add_argument(
        "--version", default=None, help="install a specific tag (default: latest)"
    )
    p_update.add_argument("--force", action="store_true", help="reinstall even if already current")
    p_update.add_argument(
        "--check", action="store_true", help="report installed vs available version, don't download"
    )
    p_update.set_defaults(func=_cmd_update)

    p_config = sub.add_parser("config", help="config utilities")
    config_sub = p_config.add_subparsers(dest="subcommand", required=True)
    p_check = config_sub.add_parser("check", help="validate config")
    p_check.add_argument("--config", default=None)
    p_check.set_defaults(func=_cmd_config_check)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except (KeyboardInterrupt, EOFError):
        print("\n⚠ Interrupted by user.", file=sys.stderr)
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
