from __future__ import annotations

from pathlib import Path


def display_path(path: str) -> str:
    """Return a user-facing path with the home directory collapsed to ~."""
    raw = str(path)
    home = Path.home().resolve()
    try:
        resolved = Path(raw).expanduser().resolve(strict=False)
    except OSError:
        return raw
    if resolved == home:
        return "~"
    try:
        rel = resolved.relative_to(home)
    except ValueError:
        return raw
    return f"~/{rel.as_posix()}"
