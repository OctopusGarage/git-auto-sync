from __future__ import annotations

import subprocess

_MARKER = "# git-auto-sync"


def cron_line(binary: str, interval_seconds: int) -> str:
    """Render a crontab line. Sub-hour intervals map to */N minutes."""
    minutes = max(1, interval_seconds // 60)
    if minutes < 60:
        schedule = f"*/{minutes} * * * *"
    else:
        hours = minutes // 60
        schedule = f"0 */{hours} * * *"
    return f"{schedule} {binary} sync"


def with_entry(existing: str, binary: str, interval_seconds: int) -> str:
    """Return crontab text with our single managed line (marked), replacing any prior one."""
    line = f"{cron_line(binary, interval_seconds)}  {_MARKER}"
    kept = [ln for ln in existing.splitlines() if _MARKER not in ln]
    kept = [ln for ln in kept if ln.strip() != ""]
    kept.append(line)
    return "\n".join(kept) + "\n"


def without_entry(existing: str) -> str:
    """Return crontab text with our managed line removed."""
    kept = [ln for ln in existing.splitlines() if _MARKER not in ln]
    return ("\n".join(kept) + "\n") if any(ln.strip() for ln in kept) else ""


def _read_crontab() -> str:
    proc = subprocess.run(["crontab", "-l"], capture_output=True, text=True)
    # crontab -l exits non-zero when no crontab exists; treat as empty
    return proc.stdout if proc.returncode == 0 else ""


def _write_crontab(text: str) -> None:
    subprocess.run(["crontab", "-"], input=text, text=True, capture_output=True, check=True)


def install_cron(binary: str, interval_seconds: int) -> str:
    _write_crontab(with_entry(_read_crontab(), binary, interval_seconds))
    return f"cron entry installed (every {interval_seconds}s)"


def uninstall_cron() -> str:
    current = _read_crontab()
    if _MARKER not in current:
        return "no cron entry installed"
    _write_crontab(without_entry(current))
    return "cron entry removed"
