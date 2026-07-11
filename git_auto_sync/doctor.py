from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path

from git_auto_sync.config import Config


@dataclass(frozen=True)
class RuntimeToolCheck:
    repo: str
    tool: str
    ok: bool
    message: str


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return ""


def required_tools_for_repo(repo_path: str | Path, git_dir: str | Path | None = None) -> set[str]:
    work_tree = Path(repo_path)
    dot_git = Path(git_dir) if git_dir else work_tree / ".git"
    tools: set[str] = set()

    config_text = _read_text(dot_git / "config")
    attrs_text = "\n".join(
        [
            _read_text(work_tree / ".gitattributes"),
            _read_text(dot_git / "info" / "attributes"),
        ]
    )
    hooks_text = ""
    hooks_dir = dot_git / "hooks"
    if hooks_dir.is_dir():
        hooks_text = "\n".join(_read_text(path) for path in hooks_dir.iterdir() if path.is_file())

    combined = "\n".join([config_text, attrs_text, hooks_text])
    if "[lfs]" in config_text or 'filter "lfs"' in config_text or "git-lfs" in combined:
        tools.add("git-lfs")
    if "git-crypt" in combined or "filter=git-crypt" in attrs_text:
        tools.add("git-crypt")
    return tools


def check_runtime_tools(config: Config, search_path: str) -> list[RuntimeToolCheck]:
    results: list[RuntimeToolCheck] = []
    for repo in config.repos:
        if not repo.push:
            continue
        repo_path = repo.work_tree or repo.path
        for tool in sorted(required_tools_for_repo(repo_path, repo.git_dir)):
            found = shutil.which(tool, path=search_path)
            if found:
                results.append(
                    RuntimeToolCheck(
                        repo=repo.path,
                        tool=tool,
                        ok=True,
                        message=f"{tool} found at {found}",
                    )
                )
            else:
                results.append(
                    RuntimeToolCheck(
                        repo=repo.path,
                        tool=tool,
                        ok=False,
                        message=f"{tool} not found on PATH: {search_path}",
                    )
                )
    return results
