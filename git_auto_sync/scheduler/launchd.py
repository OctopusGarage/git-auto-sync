from __future__ import annotations

import subprocess
from pathlib import Path

from git_auto_sync.scheduler import LABEL

DEFAULT_LAUNCHD_PATH = (
    "/opt/homebrew/bin:/opt/homebrew/sbin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"
)


def plist_content(binary: str, interval_seconds: int) -> str:
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>{LABEL}</string>
  <key>ProgramArguments</key>
  <array>
    <string>{binary}</string>
    <string>sync</string>
  </array>
  <key>EnvironmentVariables</key>
  <dict>
    <key>PATH</key><string>{DEFAULT_LAUNCHD_PATH}</string>
  </dict>
  <key>StartInterval</key><integer>{interval_seconds}</integer>
  <key>RunAtLoad</key><false/>
  <key>StandardOutPath</key><string>{Path.home()}/.git-auto-sync/launchd.out.log</string>
  <key>StandardErrorPath</key><string>{Path.home()}/.git-auto-sync/launchd.err.log</string>
</dict>
</plist>
"""


def _plist_path() -> Path:
    return Path.home() / "Library" / "LaunchAgents" / f"{LABEL}.plist"


def install_launchd(binary: str, interval_seconds: int) -> str:
    path = _plist_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    (Path.home() / ".git-auto-sync").mkdir(parents=True, exist_ok=True)
    path.write_text(plist_content(binary, interval_seconds))
    subprocess.run(["launchctl", "unload", str(path)], capture_output=True, text=True)
    subprocess.run(["launchctl", "load", str(path)], capture_output=True, text=True, check=True)
    return f"launchd agent installed at {path} (every {interval_seconds}s)"


def uninstall_launchd() -> str:
    path = _plist_path()
    if path.exists():
        subprocess.run(["launchctl", "unload", str(path)], capture_output=True, text=True)
        path.unlink()
        return f"launchd agent removed: {path}"
    return "no launchd agent installed"
