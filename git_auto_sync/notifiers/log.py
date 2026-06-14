from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path


class LogNotifier:
    def __init__(self, path: str) -> None:
        self.path = Path(path).expanduser()

    def send(self, text: str) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
        with open(self.path, "a", encoding="utf-8") as f:
            f.write(f"=== {stamp} ===\n{text}\n")
        print(text)
