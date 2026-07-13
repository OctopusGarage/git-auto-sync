from __future__ import annotations

import subprocess
from pathlib import Path

from git_auto_sync.models import FileChange, RepoConfig


class RepoRuntime:
    def __init__(self, cfg: RepoConfig):
        self.display_path = cfg.path
        self.work_tree = Path(cfg.work_tree or cfg.path)
        if cfg.git_dir:
            self._cwd = self.work_tree
            self._base_cmd = [
                "git",
                "--git-dir",
                str(Path(cfg.git_dir)),
                "--work-tree",
                str(self.work_tree),
            ]
        else:
            self._cwd = Path(cfg.path)
            self._base_cmd = ["git"]

    def _git(self, *args: str) -> subprocess.CompletedProcess:
        return subprocess.run(
            [*self._base_cmd, *args],
            cwd=str(self._cwd),
            capture_output=True,
            text=True,
        )

    def _git_ok(self, *args: str) -> tuple[bool, str]:
        proc = self._git(*args)
        if proc.returncode == 0:
            return True, ""
        return False, (proc.stderr or proc.stdout).strip()

    def current_branch(self) -> str:
        return self._git("rev-parse", "--abbrev-ref", "HEAD").stdout.strip()

    def has_changes(self, pathspecs: list[str] | None = None) -> bool:
        args = ["status", "--porcelain", "-uall"]
        if pathspecs:
            args.extend(["--", *pathspecs])
        out = self._git(*args).stdout
        return bool(out.strip())

    def list_changes(self, pathspecs: list[str] | None = None) -> list[FileChange]:
        args = ["status", "--porcelain", "-uall"]
        if pathspecs:
            args.extend(["--", *pathspecs])
        out = self._git(*args).stdout
        changes: list[FileChange] = []
        for line in out.splitlines():
            if not line.strip():
                continue
            xy = line[:2]
            path = _status_path(line)
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
            fp = self.work_tree / path
            if fp.is_file():
                size = fp.stat().st_size
            changes.append(FileChange(status=status, path=path, size_bytes=size))
        return changes

    def add_paths(self, paths: list[str]) -> tuple[bool, str]:
        if paths:
            paths_to_add = self._paths_requiring_add(paths)
            if paths_to_add:
                return self._git_ok("add", "--", *paths_to_add)
        return True, ""

    def tracked_paths(self, paths: list[str]) -> list[str]:
        if not paths:
            return []
        proc = self._git("ls-files", "--", *paths)
        if proc.returncode != 0:
            return []
        return [line for line in proc.stdout.splitlines() if line.strip()]

    def skip_worktree_paths(self, paths: list[str]) -> tuple[bool, str]:
        if not paths:
            return True, ""
        return self._git_ok("update-index", "--skip-worktree", "--", *paths)

    def _paths_requiring_add(self, paths: list[str]) -> list[str]:
        proc = self._git("status", "--porcelain", "-uall", "--", *paths)
        if proc.returncode != 0:
            return paths
        paths_to_add: list[str] = []
        for line in proc.stdout.splitlines():
            if not line.strip():
                continue
            xy = line[:2]
            path = _status_path(line)
            if xy == "??" or xy[1] != " ":
                paths_to_add.append(path)
        return paths_to_add

    def has_staged_changes(self) -> tuple[bool, str]:
        proc = self._git("diff", "--cached", "--quiet", "--exit-code")
        if proc.returncode == 0:
            return False, ""
        if proc.returncode == 1:
            return True, ""
        return False, (proc.stderr or proc.stdout).strip()

    def commit(self, message: str) -> tuple[bool, str]:
        ok, err = self._git_ok("commit", "-m", message)
        if ok or not _is_gpg_sign_error(err):
            return ok, err
        return self._git_ok("commit", "--no-gpg-sign", "-m", message)

    def pull_rebase(self) -> tuple[bool, str]:
        ok, err = self._git_ok("pull", "--rebase", "--autostash")
        if not ok:
            self._git("rebase", "--abort")
            self._git("merge", "--abort")
        return ok, err

    def push(self) -> tuple[bool, str]:
        return self._git_ok("push")


def _is_gpg_sign_error(err: str) -> bool:
    low = err.lower()
    return (
        "gpg failed to sign" in low or "cannot run gpg" in low or ("gpg" in low and "sign" in low)
    )


def _status_path(line: str) -> str:
    path = line[3:].strip()
    if "->" in path:
        path = path.split("->")[-1].strip()
    return path.strip('"')


def build_repo_runtime(cfg: RepoConfig) -> RepoRuntime:
    return RepoRuntime(cfg)
