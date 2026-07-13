from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from git_auto_sync.models import PathPolicyConfig, RepoConfig
from git_auto_sync.path_policy import validate_path_policy

DEFAULT_CONFIG_PATH = Path.home() / ".git-auto-sync" / "config.toml"

_DEFAULT_FIELDS = {
    "branch": "current",
    "ai_provider": "claude-cli",
    "ai_staging": True,
    "ai_gitignore_autowrite": True,
    "push": True,
    "notify_on": "change_or_fail",
    "tracked_ignored_policy": "leave_dirty",
}
_VALID_NOTIFY_ON = {"change_or_fail", "fail_only", "always"}
_VALID_PROVIDERS = {"claude-cli", "anthropic-api", "rules"}
_VALID_TRACKED_IGNORED_POLICIES = {"leave_dirty", "skip_worktree"}


class ConfigError(Exception):
    pass


@dataclass
class Config:
    repos: list[RepoConfig]
    notifiers: dict[str, dict]


def _resolve_env(value: Any) -> Any:
    """Recursively replace 'env:VAR' string values with the environment value."""
    if isinstance(value, str) and value.startswith("env:"):
        var = value[4:]
        if var not in os.environ:
            raise ConfigError(f"environment variable not set: {var}")
        return os.environ[var]
    if isinstance(value, dict):
        return {k: _resolve_env(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_resolve_env(v) for v in value]
    return value


def _resolve_path(value: str | None) -> str | None:
    if value is None:
        return None
    return str(Path(value).expanduser().resolve())


def _load_path_policy(raw: dict[str, Any] | None) -> PathPolicyConfig:
    if raw is None:
        return PathPolicyConfig()
    policy = PathPolicyConfig(
        mode=raw.get("mode", "all"),
        include=list(raw.get("include", [])),
        exclude=list(raw.get("exclude", [])),
        include_file=_resolve_path(raw.get("include_file")),
        exclude_file=_resolve_path(raw.get("exclude_file")),
        builtin_deny=bool(raw.get("builtin_deny", True)),
        max_file_bytes=int(raw.get("max_file_bytes", 5 * 1024 * 1024)),
    )
    try:
        validate_path_policy(policy)
    except ValueError as exc:
        raise ConfigError(str(exc)) from exc
    return policy


def _validate_repo_work_tree(repo: RepoConfig) -> None:
    if bool(repo.git_dir) != bool(repo.work_tree):
        raise ConfigError("git_dir and work_tree must be configured together")

    effective_work_tree = Path(repo.work_tree or repo.path).expanduser().resolve()
    if effective_work_tree == Path.home().resolve() and repo.path_policy.mode != "allowlist":
        label = repo.name or repo.path
        raise ConfigError(
            f'repo "{label}" uses the user home directory as its work tree; '
            'path_policy.mode = "allowlist" with include/include_file is required'
        )

    if repo.git_dir and repo.path_policy.mode != "allowlist":
        label = repo.name or repo.path
        raise ConfigError(
            f'repo "{label}" uses git_dir/work_tree; '
            'path_policy.mode = "allowlist" with include/include_file is required'
        )


def load_config(path: str | Path | None = None) -> Config:
    path = Path(path) if path else DEFAULT_CONFIG_PATH
    if not path.exists():
        raise ConfigError(f"config file not found: {path}")
    with open(path, "rb") as f:
        raw = tomllib.load(f)

    # Resolve env: refs for defaults and repos, but only for ENABLED notifiers —
    # a disabled notifier's placeholder env var must not break config loading.
    defaults_raw = _resolve_env(raw.get("defaults", {}))
    notifiers: dict[str, dict] = {}
    for name, conf in raw.get("notifiers", {}).items():
        notifiers[name] = _resolve_env(conf) if conf.get("enabled") else conf

    defaults = {**_DEFAULT_FIELDS, **defaults_raw}
    repo_entries = raw.get("repos", [])
    if not repo_entries:
        raise ConfigError("no [[repos]] configured")

    repos: list[RepoConfig] = []
    for entry in repo_entries:
        entry = _resolve_env(entry)
        if "path" not in entry:
            raise ConfigError("every [[repos]] needs a 'path'")
        merged = {**defaults, **entry}
        if merged["notify_on"] not in _VALID_NOTIFY_ON:
            raise ConfigError(f"invalid notify_on: {merged['notify_on']}")
        if merged["ai_provider"] not in _VALID_PROVIDERS:
            raise ConfigError(f"invalid ai_provider: {merged['ai_provider']}")
        if merged["tracked_ignored_policy"] not in _VALID_TRACKED_IGNORED_POLICIES:
            raise ConfigError(f"invalid tracked_ignored_policy: {merged['tracked_ignored_policy']}")
        repo = RepoConfig(
            path=str(Path(merged["path"]).expanduser().resolve()),
            name=str(merged.get("name", "")),
            git_dir=_resolve_path(merged.get("git_dir")),
            work_tree=_resolve_path(merged.get("work_tree")),
            branch=merged["branch"],
            ai_provider=merged["ai_provider"],
            ai_staging=bool(merged["ai_staging"]),
            ai_gitignore_autowrite=bool(merged["ai_gitignore_autowrite"]),
            push=bool(merged["push"]),
            notify_on=merged["notify_on"],
            tracked_ignored_policy=merged["tracked_ignored_policy"],
            path_policy=_load_path_policy(merged.get("path_policy")),
        )
        _validate_repo_work_tree(repo)
        repos.append(repo)

    return Config(repos=repos, notifiers=notifiers)
