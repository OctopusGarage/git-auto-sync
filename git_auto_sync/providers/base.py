from __future__ import annotations

from typing import Protocol

from git_auto_sync.models import FileChange


class StagingDecision:
    def __init__(self, stage: list[str], ignore: list[str]):
        self.stage = stage
        self.ignore = ignore


class Provider(Protocol):
    def analyze_staging(self, changes: list[FileChange]) -> StagingDecision: ...
    def generate_message(self, changes: list[FileChange], diff_text: str) -> str: ...
