from __future__ import annotations

import os
from pathlib import Path


def display_path(path: str) -> str:
    """Return a user-facing path with the home directory collapsed to ~."""
    raw = str(path)
    try:
        home = _home_path()
        resolved = _expand_path(raw, home).resolve(strict=False)
    except OSError:
        return raw
    if resolved == home:
        return "~"
    try:
        rel = resolved.relative_to(home)
    except ValueError:
        return raw
    return f"~/{rel.as_posix()}"


def _home_path() -> Path:
    configured_home = os.environ.get("HOME")
    return Path(configured_home).resolve(strict=False) if configured_home else Path.home().resolve()


def _expand_path(raw: str, home: Path) -> Path:
    if raw == "~":
        return home
    if raw.startswith("~/") or raw.startswith("~\\"):
        return home / raw[2:]
    return Path(raw)
