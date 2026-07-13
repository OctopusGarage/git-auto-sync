import subprocess
from pathlib import Path

from git_auto_sync import cli


def _config_file(tmp_path, repo_path, logfile):
    cfg = tmp_path / "config.toml"
    repo_path = str(Path(repo_path).as_posix())
    logfile = str(logfile.as_posix())
    cfg.write_text(f"""
[defaults]
ai_provider = "rules"
ai_staging = false
push = true

[[repos]]
path = "{repo_path}"

[notifiers.log]
enabled = true
path = "{logfile}"
""")
    return cfg


def test_sync_commits_and_notifies(git_repo, tmp_path):
    (Path(git_repo) / "x.py").write_text("print(1)\n")
    logfile = tmp_path / "sync.log"
    cfg = _config_file(tmp_path, git_repo, logfile)
    code = cli.main(["sync", "--config", str(cfg)])
    assert code == 0
    assert "Committed and pushed" in logfile.read_text(encoding="utf-8")


def test_sync_dry_run_makes_no_commit(git_repo, tmp_path):
    (Path(git_repo) / "x.py").write_text("print(1)\n")
    logfile = tmp_path / "sync.log"
    cfg = _config_file(tmp_path, git_repo, logfile)
    code = cli.main(["sync", "--config", str(cfg), "--dry-run"])
    assert code == 0
    from git_auto_sync import git_ops

    assert git_ops.has_changes(git_repo) is True  # nothing committed


def test_sync_repo_filter_matches_name(git_repo, tmp_path):
    (Path(git_repo) / "x.py").write_text("print(1)\n")
    logfile = tmp_path / "sync.log"
    cfg = tmp_path / "config.toml"
    cfg.write_text(f"""
[defaults]
ai_provider = "rules"
ai_staging = false
push = false

[[repos]]
name = "named-repo"
path = "{Path(git_repo).as_posix()}"

[notifiers.log]
enabled = true
path = "{logfile.as_posix()}"
""")

    code = cli.main(["sync", "--config", str(cfg), "--repo", "named-repo"])

    assert code == 0
    assert "Committed (not pushed)" in logfile.read_text(encoding="utf-8")


def test_config_check_ok(git_repo, tmp_path, capsys):
    logfile = tmp_path / "sync.log"
    cfg = _config_file(tmp_path, git_repo, logfile)
    code = cli.main(["config", "check", "--config", str(cfg)])
    assert code == 0
    assert "OK" in capsys.readouterr().out


def test_status_shortens_home_paths(tmp_path, monkeypatch, capsys):
    home = tmp_path / "home"
    repo = home / "repo"
    home.mkdir()
    repo.mkdir()
    monkeypatch.setenv("HOME", str(home))
    subprocess.run(["git", "init", "-b", "main", "."], cwd=repo, check=True, capture_output=True)
    cfg = tmp_path / "config.toml"
    cfg.write_text(f"""
[[repos]]
path = "{repo.as_posix()}"
""")

    code = cli.main(["status", "--config", str(cfg)])

    assert code == 0
    assert "~/repo  [HEAD]  clean" in capsys.readouterr().out


def test_config_check_reports_missing_runtime_tool(tmp_path, capsys, monkeypatch):
    repo = tmp_path / "repo"
    empty_bin = tmp_path / "empty-bin"
    empty_bin.mkdir()
    (repo / ".git").mkdir(parents=True)
    (repo / ".git" / "config").write_text(
        "[lfs]\n\trepositoryformatversion = 0\n", encoding="utf-8"
    )
    cfg = tmp_path / "config.toml"
    cfg.write_text(f"""
[defaults]
ai_provider = "rules"
ai_staging = false
push = true

[[repos]]
path = "{repo.as_posix()}"
""")
    monkeypatch.setenv("PATH", str(empty_bin))

    code = cli.main(["config", "check", "--config", str(cfg)])

    captured = capsys.readouterr()
    assert code == 1
    assert "runtime error" in captured.err
    assert "git-lfs" in captured.err
    assert str(repo) in captured.err
