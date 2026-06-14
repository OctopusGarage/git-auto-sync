from __future__ import annotations

import subprocess
from pathlib import Path

from git_auto_sync.models import FileChange


def _git(repo: str | Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", *args],
        cwd=str(repo),
        capture_output=True,
        text=True,
    )


def _git_ok(repo: str | Path, *args: str) -> tuple[bool, str]:
    proc = _git(repo, *args)
    if proc.returncode == 0:
        return True, ""
    return False, (proc.stderr or proc.stdout).strip()


def current_branch(repo: str | Path) -> str:
    return _git(repo, "rev-parse", "--abbrev-ref", "HEAD").stdout.strip()


def has_changes(repo: str | Path) -> bool:
    out = _git(repo, "status", "--porcelain").stdout
    return bool(out.strip())


def list_changes(repo: str | Path) -> list[FileChange]:
    """Parse `git status --porcelain` into FileChange records."""
    out = _git(repo, "status", "--porcelain").stdout
    changes: list[FileChange] = []
    for line in out.splitlines():
        if not line.strip():
            continue
        xy = line[:2]
        path = line[3:].strip()
        if "->" in path:  # rename "old -> new"
            path = path.split("->")[-1].strip()
        path = path.strip('"')
        if xy == "??":
            status = "A"
        elif "D" in xy:
            status = "D"
        elif "A" in xy:
            status = "A"
        elif "R" in xy:
            status = "R"
        else:
            status = "M"
        size = 0
        fp = Path(repo) / path
        if fp.is_file():
            size = fp.stat().st_size
        changes.append(FileChange(status=status, path=path, size_bytes=size))
    return changes


def add_all(repo: str | Path) -> None:
    _git(repo, "add", "-A")


def add_paths(repo: str | Path, paths: list[str]) -> None:
    if paths:
        _git(repo, "add", "--", *paths)


def commit(repo: str | Path, message: str) -> tuple[bool, str]:
    return _git_ok(repo, "commit", "-m", message)


def pull_rebase(repo: str | Path) -> tuple[bool, str]:
    ok, err = _git_ok(repo, "pull", "--rebase")
    if not ok:
        # abort whichever operation pull started so the tree is never left half-done
        _git(repo, "rebase", "--abort")
        _git(repo, "merge", "--abort")
    return ok, err


def push(repo: str | Path) -> tuple[bool, str]:
    return _git_ok(repo, "push")
