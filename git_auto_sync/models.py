from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class FileChange:
    """One changed path in a repo's working tree."""

    status: str  # "A" added/untracked, "M" modified, "D" deleted, "R" renamed
    path: str
    size_bytes: int = 0  # best-effort size of the working-tree file (0 if deleted/unknown)


@dataclass
class PathPolicyConfig:
    mode: str = "all"  # "all" keeps existing behaviour; "allowlist" requires include rules.
    include: list[str] = field(default_factory=list)
    exclude: list[str] = field(default_factory=list)
    include_file: str | None = None
    exclude_file: str | None = None
    builtin_deny: bool = False
    max_file_bytes: int = 0


@dataclass
class RepoConfig:
    path: str  # expanded absolute path
    name: str = ""
    git_dir: str | None = None
    work_tree: str | None = None
    branch: str = "current"
    ai_provider: str = "claude-cli"
    ai_staging: bool = True
    ai_gitignore_autowrite: bool = True
    push: bool = True
    notify_on: str = "change_or_fail"
    path_policy: PathPolicyConfig = field(default_factory=PathPolicyConfig)


@dataclass
class RepoResult:
    path: str
    # one of: "skipped", "committed", "committed_pushed", "failed"
    status: str
    message: str = ""  # commit message summary (first line)
    error: str = ""  # failure reason if status == "failed"
    ignored_paths: list[str] = field(default_factory=list)
    blocked_paths: list[str] = field(default_factory=list)


@dataclass
class RunSummary:
    results: list[RepoResult] = field(default_factory=list)

    @property
    def changed(self) -> bool:
        return any(r.status in ("committed", "committed_pushed") for r in self.results)

    @property
    def failed(self) -> bool:
        return any(r.status == "failed" for r in self.results)
