from __future__ import annotations

from git_auto_sync.models import RunSummary
from git_auto_sync.notifiers.lark import LarkNotifier
from git_auto_sync.notifiers.log import LogNotifier
from git_auto_sync.notifiers.telegram import TelegramNotifier

_STATUS_LABEL = {
    "skipped": "⏭️ No changes",
    "committed": "✅ Committed (not pushed)",
    "committed_pushed": "🚀 Committed and pushed",
    "failed": "❌ Failed",
}


def format_summary(summary: RunSummary) -> str:
    lines = ["git-auto-sync sync result:"]
    for r in summary.results:
        label = _STATUS_LABEL.get(r.status, r.status)
        line = f"{label}  {r.path}"
        if r.message:
            line += f"\n  {r.message.splitlines()[0]}"
        if r.error:
            line += f"\n  Reason: {r.error}"
        if r.ignored_paths:
            line += f"\n  Ignored: {', '.join(r.ignored_paths)}"
        lines.append(line)
    return "\n".join(lines)


def build_notifiers(config: dict) -> list:
    notifiers = []
    for name, conf in config.items():
        if not conf.get("enabled"):
            continue
        if name == "log":
            notifiers.append(LogNotifier(conf["path"]))
        elif name == "telegram":
            notifiers.append(TelegramNotifier(conf["bot_token"], conf["chat_id"]))
        elif name == "lark":
            notifiers.append(LarkNotifier(conf["webhook"]))
    return notifiers
