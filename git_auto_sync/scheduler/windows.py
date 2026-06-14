from __future__ import annotations

import shutil
import subprocess

TASK_NAME = "OctopusGarage.git-auto-sync"


def _ps_quote(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def _powershell() -> str:
    return shutil.which("powershell.exe") or shutil.which("pwsh") or "powershell.exe"


def task_script(binary: str, interval_seconds: int) -> str:
    quoted_binary = _ps_quote(binary)
    quoted_task_name = _ps_quote(TASK_NAME)
    return f"""
$Action = New-ScheduledTaskAction -Execute {quoted_binary} -Argument 'sync'
$Trigger = New-ScheduledTaskTrigger `
  -Once `
  -At (Get-Date).AddMinutes(1) `
  -RepetitionInterval (New-TimeSpan -Seconds {interval_seconds}) `
  -RepetitionDuration ([TimeSpan]::MaxValue)
$Settings = New-ScheduledTaskSettingsSet -MultipleInstances IgnoreNew -StartWhenAvailable
Register-ScheduledTask `
  -TaskName {quoted_task_name} `
  -Action $Action `
  -Trigger $Trigger `
  -Settings $Settings `
  -Description 'Periodic git-auto-sync run' `
  -Force | Out-Null
"""


def unregister_script() -> str:
    return (
        f"Unregister-ScheduledTask -TaskName {_ps_quote(TASK_NAME)} "
        "-Confirm:$false -ErrorAction SilentlyContinue"
    )


def _run_powershell(script: str) -> None:
    subprocess.run(
        [_powershell(), "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", script],
        capture_output=True,
        text=True,
        check=True,
    )


def install_windows(binary: str, interval_seconds: int) -> str:
    _run_powershell(task_script(binary, interval_seconds))
    return f"Windows scheduled task installed: {TASK_NAME} (every {interval_seconds}s)"


def uninstall_windows() -> str:
    _run_powershell(unregister_script())
    return f"Windows scheduled task removed: {TASK_NAME}"
