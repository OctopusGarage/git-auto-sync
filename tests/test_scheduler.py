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


def test_plist_contains_interval_and_binary():
    text = plist_content(binary="/usr/local/bin/git-auto-sync", interval_seconds=1800)
    assert "git-auto-sync" in text
    assert "<integer>1800</integer>" in text
    assert "com.octopusgarage.git-auto-sync" in text


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
    assert "/usr/bin/backup" in out                 # unrelated line preserved
    assert out.count("# git-auto-sync") == 1         # only one managed line
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
