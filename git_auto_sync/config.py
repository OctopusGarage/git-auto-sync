from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from git_auto_sync.models import RepoConfig

DEFAULT_CONFIG_PATH = Path.home() / ".git-auto-sync" / "config.toml"

_DEFAULT_FIELDS = {
    "branch": "current",
    "ai_provider": "claude-cli",
    "ai_staging": True,
    "ai_gitignore_autowrite": True,
    "push": True,
    "notify_on": "change_or_fail",
}
_VALID_NOTIFY_ON = {"change_or_fail", "fail_only", "always"}
_VALID_PROVIDERS = {"claude-cli", "anthropic-api", "rules"}


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
        repos.append(RepoConfig(
            path=str(Path(merged["path"]).expanduser().resolve()),
            branch=merged["branch"],
            ai_provider=merged["ai_provider"],
            ai_staging=bool(merged["ai_staging"]),
            ai_gitignore_autowrite=bool(merged["ai_gitignore_autowrite"]),
            push=bool(merged["push"]),
            notify_on=merged["notify_on"],
        ))

    return Config(repos=repos, notifiers=notifiers)
