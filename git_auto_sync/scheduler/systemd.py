from __future__ import annotations

import subprocess
from pathlib import Path

_UNIT = "git-auto-sync"


def timer_content(binary: str, interval_seconds: int) -> tuple[str, str]:
    service = f"""[Unit]
Description=git-auto-sync one-shot

[Service]
Type=oneshot
ExecStart={binary} sync
"""
    timer = f"""[Unit]
Description=git-auto-sync periodic timer

[Timer]
OnBootSec=120
OnUnitActiveSec={interval_seconds}

[Install]
WantedBy=timers.target
"""
    return service, timer


def _unit_dir() -> Path:
    return Path.home() / ".config" / "systemd" / "user"


def install_systemd(binary: str, interval_seconds: int) -> str:
    service, timer = timer_content(binary, interval_seconds)
    d = _unit_dir()
    d.mkdir(parents=True, exist_ok=True)
    (Path.home() / ".git-auto-sync").mkdir(parents=True, exist_ok=True)
    (d / f"{_UNIT}.service").write_text(service)
    (d / f"{_UNIT}.timer").write_text(timer)
    subprocess.run(["systemctl", "--user", "daemon-reload"], capture_output=True, text=True)
    subprocess.run(
        ["systemctl", "--user", "enable", "--now", f"{_UNIT}.timer"],
        capture_output=True,
        text=True,
        check=True,
    )
    return f"systemd timer installed in {d} (every {interval_seconds}s)"


def uninstall_systemd() -> str:
    d = _unit_dir()
    subprocess.run(
        ["systemctl", "--user", "disable", "--now", f"{_UNIT}.timer"],
        capture_output=True,
        text=True,
    )
    removed = False
    for name in (f"{_UNIT}.service", f"{_UNIT}.timer"):
        p = d / name
        if p.exists():
            p.unlink()
            removed = True
    subprocess.run(["systemctl", "--user", "daemon-reload"], capture_output=True, text=True)
    return "systemd timer removed" if removed else "no systemd timer installed"
