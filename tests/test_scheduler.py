import pytest

import git_auto_sync.scheduler as scheduler
from git_auto_sync.scheduler import parse_interval_seconds
from git_auto_sync.scheduler.cron import cron_line
from git_auto_sync.scheduler.launchd import plist_content
from git_auto_sync.scheduler.systemd import timer_content


def test_parse_interval():
    assert parse_interval_seconds("30m") == 1800
    assert parse_interval_seconds("1h") == 3600
    assert parse_interval_seconds("90s") == 90
    with pytest.raises(ValueError):
        parse_interval_seconds("banana")
    with pytest.raises(ValueError):
        parse_interval_seconds("30")  # missing unit
    with pytest.raises(ValueError):
        parse_interval_seconds("0m")  # non-positive


def test_binary_prefers_stable_user_launcher(monkeypatch, tmp_path):
    launcher = tmp_path / ".local" / "bin" / "git-auto-sync"
    launcher.parent.mkdir(parents=True)
    launcher.write_text("#!/bin/sh\n", encoding="utf-8")
    launcher.chmod(0o755)

    monkeypatch.setattr(scheduler.Path, "home", lambda: tmp_path)
    monkeypatch.setattr(
        scheduler.shutil,
        "which",
        lambda name: "/tmp/project/.venv/bin/git-auto-sync",
    )

    assert scheduler._binary() == str(launcher)


def test_binary_ignores_non_executable_user_launcher(monkeypatch, tmp_path):
    launcher = tmp_path / ".local" / "bin" / "git-auto-sync"
    launcher.parent.mkdir(parents=True)
    launcher.write_text("#!/bin/sh\n", encoding="utf-8")
    launcher.chmod(0o644)

    monkeypatch.setattr(scheduler.Path, "home", lambda: tmp_path)
    monkeypatch.setattr(
        scheduler.shutil,
        "which",
        lambda name: "/tmp/project/.venv/bin/git-auto-sync",
    )

    assert scheduler._binary() == "/tmp/project/.venv/bin/git-auto-sync"


def test_plist_contains_interval_and_binary():
    text = plist_content(binary="/usr/local/bin/git-auto-sync", interval_seconds=1800)
    assert "git-auto-sync" in text
    assert "<integer>1800</integer>" in text
    assert "com.octopusgarage.git-auto-sync" in text


def test_plist_sets_path_for_homebrew_tools():
    text = plist_content(binary="/usr/local/bin/git-auto-sync", interval_seconds=1800)

    assert "<key>EnvironmentVariables</key>" in text
    assert "<key>PATH</key>" in text
    assert "/opt/homebrew/bin" in text
    assert "/usr/local/bin" in text
    assert "/usr/bin" in text
    assert "/bin" in text


def test_launchd_install_bootstraps_user_domain(monkeypatch, tmp_path):
    import git_auto_sync.scheduler.launchd as launchd

    calls = []

    monkeypatch.setattr(launchd.Path, "home", lambda: tmp_path)
    monkeypatch.setattr(launchd.os, "getuid", lambda: 501)
    monkeypatch.setattr(
        launchd.subprocess,
        "run",
        lambda args, **kwargs: calls.append((args, kwargs)),
    )

    result = launchd.install_launchd("/usr/local/bin/git-auto-sync", 1800)
    plist = tmp_path / "Library" / "LaunchAgents" / "com.octopusgarage.git-auto-sync.plist"

    assert result == f"launchd agent installed at {plist} (every 1800s)"
    assert calls == [
        (
            [
                "launchctl",
                "bootout",
                "gui/501",
                str(plist),
            ],
            {"capture_output": True, "text": True},
        ),
        (
            [
                "launchctl",
                "bootstrap",
                "gui/501",
                str(plist),
            ],
            {"capture_output": True, "text": True, "check": True},
        ),
        (
            [
                "launchctl",
                "enable",
                "gui/501/com.octopusgarage.git-auto-sync",
            ],
            {"capture_output": True, "text": True, "check": True},
        ),
    ]


def test_systemd_timer_has_oncalendar_or_onunit():
    service, timer = timer_content(binary="/usr/local/bin/git-auto-sync", interval_seconds=1800)
    assert "ExecStart=/usr/local/bin/git-auto-sync sync" in service
    assert "OnUnitActiveSec=1800" in timer


def test_cron_line_format():
    line = cron_line(binary="/usr/local/bin/git-auto-sync", interval_seconds=1800)
    assert "*/30 * * * *" in line
    assert "git-auto-sync sync" in line


def test_with_entry_replaces_prior_managed_line():
    from git_auto_sync.scheduler.cron import with_entry

    existing = "0 5 * * * /usr/bin/backup\n*/10 * * * * /old/git-auto-sync sync  # git-auto-sync\n"
    out = with_entry(existing, "/usr/local/bin/git-auto-sync", 1800)
    assert "/usr/bin/backup" in out  # unrelated line preserved
    assert out.count("# git-auto-sync") == 1  # only one managed line
    assert "*/30 * * * * /usr/local/bin/git-auto-sync sync" in out


def test_without_entry_removes_managed_line_only():
    from git_auto_sync.scheduler.cron import without_entry

    existing = "0 5 * * * /usr/bin/backup\n*/30 * * * * x sync  # git-auto-sync\n"
    out = without_entry(existing)
    assert "/usr/bin/backup" in out
    assert "# git-auto-sync" not in out


def test_windows_task_script_registers_interval_and_launcher():
    from git_auto_sync.scheduler.windows import TASK_NAME, task_script

    binary = r"C:\Users\me\.local\bin\git-auto-sync.cmd"
    script = task_script(binary=binary, interval_seconds=1800)

    assert TASK_NAME == "OctopusGarage.git-auto-sync"
    assert "New-ScheduledTaskAction" in script
    assert f"-Execute '{binary}'" in script
    assert "-Argument 'sync'" in script
    assert "New-TimeSpan -Seconds 1800" in script
    assert "Register-ScheduledTask" in script
    assert "-TaskName 'OctopusGarage.git-auto-sync'" in script
    assert "-Force" in script


def test_windows_task_script_escapes_single_quotes():
    from git_auto_sync.scheduler.windows import task_script

    script = task_script(binary=r"C:\Users\O'Neil\git-auto-sync.cmd", interval_seconds=90)

    assert "O''Neil" in script


def test_scheduler_dispatches_windows_install(monkeypatch):
    import git_auto_sync.scheduler.windows as windows

    calls = []
    monkeypatch.setattr(scheduler.sys, "platform", "win32")
    monkeypatch.setattr(scheduler, "_binary", lambda: r"C:\bin\git-auto-sync.cmd")
    monkeypatch.setattr(
        windows,
        "install_windows",
        lambda binary, seconds: calls.append((binary, seconds)) or "installed",
    )

    assert scheduler.install("30m") == "installed"
    assert calls == [(r"C:\bin\git-auto-sync.cmd", 1800)]


def test_scheduler_dispatches_windows_uninstall(monkeypatch):
    import git_auto_sync.scheduler.windows as windows

    monkeypatch.setattr(scheduler.sys, "platform", "win32")
    monkeypatch.setattr(windows, "uninstall_windows", lambda: "removed")

    assert scheduler.uninstall() == "removed"
