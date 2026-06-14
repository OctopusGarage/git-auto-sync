from __future__ import annotations

import requests


class LarkNotifier:
    def __init__(self, webhook: str) -> None:
        self.webhook = webhook

    def send(self, text: str) -> None:
        resp = requests.post(
            self.webhook,
            json={"msg_type": "text", "content": {"text": text}},
            timeout=30,
        )
        resp.raise_for_status()
