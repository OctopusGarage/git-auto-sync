from __future__ import annotations

import fnmatch
from dataclasses import dataclass
from pathlib import Path

from git_auto_sync.models import FileChange, PathPolicyConfig


@dataclass
class PathPolicyResult:
    stage: list[FileChange]
    ignored: list[str]
    blocked: list[str]


_BUILTIN_DENY = [
    ".env",
    ".env.*",
    ".npmrc",
    ".mylogin.cnf",
    ".netrc",
    ".zsh_history",
    ".bash_history",
    ".mysql_history",
    ".python_history",
    ".config/gh/hosts.yml",
    ".config/gcloud/**",
    ".config/clash/**",
    ".ssh/id_*",
    "*.pem",
    "*.key",
    "*.p12",
    "*credentials*",
    "*token*",
    "*.log",
    ".DS_Store",
]


def _read_rules(path: str | None) -> list[str]:
    if not path:
        return []
    p = Path(path).expanduser()
    if not p.exists():
        return []
    return [
        line.strip()
        for line in p.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]


def _normalize(path: str) -> str:
    path = path.replace("\\", "/")
    while path.startswith("./"):
        path = path[2:]
    return path.lstrip("/")


def _match_one(path: str, pattern: str) -> bool:
    path = _normalize(path)
    pattern = _normalize(pattern.rstrip())
    if pattern.endswith("/"):
        pattern = f"{pattern}**"
    if pattern.startswith("/"):
        pattern = pattern[1:]
    if pattern.endswith("/**") and path.startswith(pattern[:-3].rstrip("/") + "/"):
        return True
    if "/" not in pattern:
        return any(fnmatch.fnmatchcase(part, pattern) for part in path.split("/"))
    return fnmatch.fnmatchcase(path, pattern)


def _matches(path: str, rules: list[str]) -> bool:
    matched = False
    for rule in rules:
        negated = rule.startswith("!")
        pattern = rule[1:] if negated else rule
        if _match_one(path, pattern):
            matched = not negated
    return matched


def _has_include_rules(policy: PathPolicyConfig) -> bool:
    return bool(policy.include or _read_rules(policy.include_file))


def validate_path_policy(policy: PathPolicyConfig) -> None:
    if policy.mode not in {"all", "allowlist"}:
        raise ValueError(f"invalid path_policy.mode: {policy.mode}")
    if policy.mode == "allowlist" and not _has_include_rules(policy):
        raise ValueError('path_policy.mode = "allowlist" requires include or include_file')


def status_pathspecs(policy: PathPolicyConfig | None) -> list[str] | None:
    if not policy or policy.mode != "allowlist":
        return None
    rules = [*policy.include, *_read_rules(policy.include_file)]
    pathspecs = [rule.rstrip() for rule in rules if rule.rstrip() and not rule.startswith("!")]
    return pathspecs


def apply_path_policy(
    changes: list[FileChange],
    policy: PathPolicyConfig | None,
) -> PathPolicyResult:
    policy = policy or PathPolicyConfig()
    validate_path_policy(policy)

    include_rules = [*policy.include, *_read_rules(policy.include_file)]
    exclude_rules = [*policy.exclude, *_read_rules(policy.exclude_file)]
    deny_rules = _BUILTIN_DENY if policy.builtin_deny else []

    stage: list[FileChange] = []
    ignored: list[str] = []
    blocked: list[str] = []
    for change in changes:
        if policy.max_file_bytes and change.size_bytes > policy.max_file_bytes:
            blocked.append(change.path)
        elif deny_rules and _matches(change.path, deny_rules):
            blocked.append(change.path)
        elif exclude_rules and _matches(change.path, exclude_rules):
            ignored.append(change.path)
        elif policy.mode == "allowlist" and not _matches(change.path, include_rules):
            ignored.append(change.path)
        else:
            stage.append(change)

    return PathPolicyResult(stage=stage, ignored=ignored, blocked=blocked)
