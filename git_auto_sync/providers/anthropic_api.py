from __future__ import annotations

import json
import os

import requests

from git_auto_sync.models import FileChange
from git_auto_sync.providers.base import StagingDecision
from git_auto_sync.providers.claude_cli import (
    _format_changes,
    _load_prompt,
    parse_staging_json,
)

_API_URL = "https://api.anthropic.com/v1/messages"
_MODEL = "claude-opus-4-8"


class AnthropicApiProvider:
    def __init__(self) -> None:
        self._key = os.environ.get("ANTHROPIC_API_KEY", "")

    def _raw(self, prompt: str) -> str:
        if not self._key:
            raise RuntimeError("ANTHROPIC_API_KEY not set")
        resp = requests.post(
            _API_URL,
            headers={
                "x-api-key": self._key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            data=json.dumps(
                {
                    "model": _MODEL,
                    "max_tokens": 512,
                    "messages": [{"role": "user", "content": prompt}],
                }
            ),
            timeout=60,
        )
        resp.raise_for_status()
        return resp.json()["content"][0]["text"].strip()

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
