from __future__ import annotations

from git_auto_sync.models import FileChange
from git_auto_sync.providers.base import StagingDecision
from git_auto_sync.providers.rules import RulesProvider


class _FallbackProvider:
    """Wraps a provider; on any error, falls back to RulesProvider."""

    def __init__(self, inner) -> None:
        self.inner = inner
        self._rules = RulesProvider()

    def analyze_staging(self, changes: list[FileChange]) -> StagingDecision:
        try:
            return self.inner.analyze_staging(changes)
        except Exception:
            return self._rules.analyze_staging(changes)

    def generate_message(self, changes: list[FileChange], diff_text: str) -> str:
        try:
            return self.inner.generate_message(changes, diff_text)
        except Exception:
            return self._rules.generate_message(changes, diff_text)


def build_provider(name: str):
    if name == "rules":
        return RulesProvider()
    if name == "claude-cli":
        from git_auto_sync.providers.claude_cli import ClaudeCliProvider
        return _FallbackProvider(ClaudeCliProvider())
    if name == "anthropic-api":
        from git_auto_sync.providers.anthropic_api import AnthropicApiProvider
        return _FallbackProvider(AnthropicApiProvider())
    raise ValueError(f"unknown provider: {name}")
