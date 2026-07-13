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
    out = _git(repo, "status", "--porcelain", "-uall").stdout
    return bool(out.strip())


def list_changes(repo: str | Path) -> list[FileChange]:
    """Parse `git status --porcelain` into FileChange records."""
    out = _git(repo, "status", "--porcelain", "-uall").stdout
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


def add_all(repo: str | Path) -> tuple[bool, str]:
    return _git_ok(repo, "add", "-A")


def add_paths(repo: str | Path, paths: list[str]) -> tuple[bool, str]:
    if paths:
        return _git_ok(repo, "add", "--", *paths)
    return True, ""


def _is_gpg_sign_error(err: str) -> bool:
    low = err.lower()
    return (
        "gpg failed to sign" in low or "cannot run gpg" in low or ("gpg" in low and "sign" in low)
    )


def commit(repo: str | Path, message: str) -> tuple[bool, str]:
    ok, err = _git_ok(repo, "commit", "-m", message)
    if ok or not _is_gpg_sign_error(err):
        return ok, err
    # Signing can fail in headless/background runs (gpg not on PATH, pinentry
    # unavailable, or the gpg-agent cache cleared after a reboot). Fall back to
    # an unsigned commit so the sync still goes through.
    return _git_ok(repo, "commit", "--no-gpg-sign", "-m", message)


def pull_rebase(repo: str | Path) -> tuple[bool, str]:
    ok, err = _git_ok(repo, "pull", "--rebase", "--autostash")
    if not ok:
        # abort whichever operation pull started so the tree is never left half-done
        _git(repo, "rebase", "--abort")
        _git(repo, "merge", "--abort")
    return ok, err


def push(repo: str | Path) -> tuple[bool, str]:
    return _git_ok(repo, "push")
