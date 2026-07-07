from __future__ import annotations

import re
import shutil
import sys

_INTERVAL_RE = re.compile(r"^(\d+)([smh])$")
_UNIT_SECONDS = {"s": 1, "m": 60, "h": 3600}
LABEL = "com.octopusgarage.git-auto-sync"


def parse_interval_seconds(interval: str) -> int:
    m = _INTERVAL_RE.match(interval.strip())
    if not m:
        raise ValueError(f"invalid interval: {interval!r} (use forms like 30m, 1h, 90s)")
    seconds = int(m.group(1)) * _UNIT_SECONDS[m.group(2)]
    if seconds <= 0:
        raise ValueError(f"interval must be positive: {interval!r}")
    return seconds


def _binary() -> str:
    return shutil.which("git-auto-sync") or "git-auto-sync"


def install(interval: str) -> str:
    """Generate and install a native schedule. Returns a human description."""
    seconds = parse_interval_seconds(interval)
    binary = _binary()
    if sys.platform == "darwin":
        from git_auto_sync.scheduler.launchd import install_launchd

        return install_launchd(binary, seconds)
    if sys.platform.startswith("linux"):
        if shutil.which("systemctl"):
            from git_auto_sync.scheduler.systemd import install_systemd

            return install_systemd(binary, seconds)
        from git_auto_sync.scheduler.cron import install_cron

        return install_cron(binary, seconds)
    if sys.platform == "win32":
        from git_auto_sync.scheduler.windows import install_windows

        return install_windows(binary, seconds)
    raise RuntimeError(f"unsupported platform for install: {sys.platform}")


def uninstall() -> str:
    if sys.platform == "darwin":
        from git_auto_sync.scheduler.launchd import uninstall_launchd

        return uninstall_launchd()
    if sys.platform.startswith("linux"):
        if shutil.which("systemctl"):
            from git_auto_sync.scheduler.systemd import uninstall_systemd

            return uninstall_systemd()
        from git_auto_sync.scheduler.cron import uninstall_cron

        return uninstall_cron()
    if sys.platform == "win32":
        from git_auto_sync.scheduler.windows import uninstall_windows

        return uninstall_windows()
    raise RuntimeError(f"unsupported platform for uninstall: {sys.platform}")
