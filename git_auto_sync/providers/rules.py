from __future__ import annotations

import re

from git_auto_sync.models import FileChange
from git_auto_sync.providers.base import StagingDecision

# Files that should almost never be committed automatically.
_SECRET_PATTERNS = [
    re.compile(r"(^|/)\.env(\.|$)"),
    re.compile(r"\.pem$"),
    re.compile(r"\.key$"),
    re.compile(r"(^|/)id_rsa"),
    re.compile(r"(^|/)id_ed25519"),
    re.compile(r"\.p12$"),
    re.compile(r"credentials(\.|$)"),
]
_ARTIFACT_PATTERNS = [
    re.compile(r"(^|/)node_modules/"),
    re.compile(r"(^|/)__pycache__/"),
    re.compile(r"(^|/)\.venv/"),
    re.compile(r"(^|/)dist/"),
    re.compile(r"(^|/)build/"),
    re.compile(r"\.pyc$"),
    re.compile(r"\.log$"),
    re.compile(r"(^|/)\.DS_Store$"),
]
_LARGE_FILE_BYTES = 5 * 1024 * 1024  # 5 MB


def _should_ignore(change: FileChange) -> bool:
    path = change.path
    for pat in _SECRET_PATTERNS + _ARTIFACT_PATTERNS:
        if pat.search(path):
            return True
    if change.size_bytes > _LARGE_FILE_BYTES:
        return True
    return False


def _classify(change: FileChange) -> tuple[str, str]:
    """Return (conventional_type, english_description) for one change."""
    path, status = change.path, change.status
    if path == ".gitignore" or path.endswith("/.gitignore"):
        return "chore", "Update .gitignore"
    if path.endswith(".md") or path.startswith("docs/"):
        verb = {"A": "Add", "M": "Update", "D": "Delete"}.get(status, "Modify")
        return "docs", f"{verb} documentation {path}"
    if status == "A":
        return "feat", f"Add {path}"
    if status == "D":
        return "chore", f"Delete {path}"
    return "chore", f"Update {path}"


class RulesProvider:
    def analyze_staging(self, changes: list[FileChange]) -> StagingDecision:
        stage, ignore = [], []
        for c in changes:
            if _should_ignore(c):
                ignore.append(c.path)
            else:
                stage.append(c.path)
        return StagingDecision(stage=stage, ignore=ignore)

    def generate_message(self, changes: list[FileChange], diff_text: str) -> str:
        staged = [c for c in changes if not _should_ignore(c)]
        if not staged:
            return "chore: Sync changes"
        main_type, main_desc = _classify(staged[0])
        lines = [f"{main_type}: {main_desc}"]
        for c in staged[1:]:
            _, desc = _classify(c)
            lines.append(f"- {desc}")
        return "\n".join(lines)
