from __future__ import annotations

import json
import shutil
import subprocess
from importlib.resources import files

from git_auto_sync.models import FileChange
from git_auto_sync.providers.base import StagingDecision


def _load_prompt(name: str) -> str:
    return files("git_auto_sync.prompts").joinpath(name).read_text(encoding="utf-8")


def _format_changes(changes: list[FileChange]) -> str:
    return "\n".join(f"{c.status}\t{c.path}\t{c.size_bytes}" for c in changes)


def parse_staging_json(text: str) -> StagingDecision:
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end == -1:
        raise ValueError("no JSON object in staging response")
    obj = json.loads(text[start : end + 1])
    return StagingDecision(stage=list(obj.get("stage", [])), ignore=list(obj.get("ignore", [])))


class ClaudeCliProvider:
    def __init__(self) -> None:
        self._bin = shutil.which("claude")

    def _raw(self, prompt: str) -> str:
        if not self._bin:
            raise RuntimeError("claude CLI not found on PATH")
        proc = subprocess.run(
            [self._bin, "-p", "--bare", prompt],
            capture_output=True,
            text=True,
            timeout=120,
        )
        if proc.returncode != 0 or not proc.stdout.strip():
            raise RuntimeError(proc.stderr.strip() or "empty claude output")
        return proc.stdout.strip()

    # Indirection points so tests can monkeypatch.
    def _raw_message(self, prompt: str) -> str:
        return self._raw(prompt)

    def _raw_staging(self, prompt: str) -> str:
        return self._raw(prompt)

    def analyze_staging(self, changes: list[FileChange]) -> StagingDecision:
        prompt = _load_prompt("staging.md").replace("{changes}", _format_changes(changes))
        return parse_staging_json(self._raw_staging(prompt))

    def generate_message(self, changes: list[FileChange], diff_text: str) -> str:
        prompt = (
            _load_prompt("commit.md")
            .replace("{changes}", _format_changes(changes))
            .replace("{diff}", diff_text or "(none)")
        )
        return self._raw_message(prompt)
