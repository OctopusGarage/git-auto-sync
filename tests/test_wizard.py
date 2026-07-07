"""Tests for git_auto_sync.wizard pure helpers."""

from __future__ import annotations

import subprocess
from pathlib import Path

from git_auto_sync.config import load_config
from git_auto_sync.wizard import _resolve_repo_token, render_config_toml, scan_git_repos

# ---------------------------------------------------------------------------
# scan_git_repos
# ---------------------------------------------------------------------------


def test_scan_git_repos_finds_git_dirs(tmp_path):
    """Two git-init'd subdirs are returned; a plain dir is excluded."""
    repo_a = tmp_path / "alpha"
    repo_b = tmp_path / "beta"
    plain = tmp_path / "plain"
    for d in (repo_a, repo_b, plain):
        d.mkdir()
    # initialise as git repos
    subprocess.run(["git", "init", str(repo_a)], check=True, capture_output=True)
    subprocess.run(["git", "init", str(repo_b)], check=True, capture_output=True)

    result = scan_git_repos(tmp_path)
    assert result == sorted([str(repo_a.resolve()), str(repo_b.resolve())])
    assert str(plain.resolve()) not in result


def test_scan_git_repos_nonexistent_parent_returns_empty():
    result = scan_git_repos("/does/not/exist/at/all/xyz_nonexistent")
    assert result == []


def test_scan_git_repos_returns_sorted(tmp_path):
    """Results are alphabetically sorted regardless of creation order."""
    for name in ("zebra", "apple", "mango"):
        d = tmp_path / name
        d.mkdir()
        subprocess.run(["git", "init", str(d)], check=True, capture_output=True)

    result = scan_git_repos(tmp_path)
    assert result == sorted(result)


def test_scan_git_repos_depth2(tmp_path):
    """Repos at depth 1 and depth 2 are both found; plain dirs at depth 2 excluded."""
    # depth-1 repo: parent/repoB
    repo_b = tmp_path / "repoB"
    repo_b.mkdir()
    subprocess.run(["git", "init", str(repo_b)], check=True, capture_output=True)

    # depth-2 repo: parent/org/repoA
    org = tmp_path / "org"
    org.mkdir()
    repo_a = org / "repoA"
    repo_a.mkdir()
    subprocess.run(["git", "init", str(repo_a)], check=True, capture_output=True)

    # depth-2 plain dir: parent/org/plaindir (no .git)
    plain = org / "plaindir"
    plain.mkdir()

    result = scan_git_repos(tmp_path)
    expected = sorted([str(repo_a.resolve()), str(repo_b.resolve())])
    assert result == expected
    assert str(plain.resolve()) not in result


# ---------------------------------------------------------------------------
# render_config_toml — round-trip through load_config
# ---------------------------------------------------------------------------


def test_render_config_toml_no_notifiers(tmp_path):
    """Render with two repos, no telegram/lark; load_config must succeed."""
    repo1 = str(tmp_path / "repo1")
    repo2 = str(tmp_path / "repo2")
    Path(repo1).mkdir()
    Path(repo2).mkdir()

    toml = render_config_toml(
        repos=[repo1, repo2],
        ai_provider="rules",
        notify_on="change_or_fail",
        log_path=str(tmp_path / "sync.log"),
        telegram=None,
        lark=None,
    )
    cfg_path = tmp_path / "config.toml"
    cfg_path.write_text(toml)

    cfg = load_config(cfg_path)
    assert len(cfg.repos) == 2
    assert "log" in cfg.notifiers
    # telegram & lark present but disabled — load_config keeps them unresolved
    assert "telegram" in cfg.notifiers
    assert cfg.notifiers["telegram"].get("enabled") is False
    assert "lark" in cfg.notifiers
    assert cfg.notifiers["lark"].get("enabled") is False


def test_render_config_toml_with_telegram(tmp_path):
    """Literal telegram credentials round-trip correctly."""
    repo1 = str(tmp_path / "repo1")
    Path(repo1).mkdir()

    toml = render_config_toml(
        repos=[repo1],
        ai_provider="claude-cli",
        notify_on="fail_only",
        log_path=str(tmp_path / "sync.log"),
        telegram={"bot_token": "LITERAL_TOKEN", "chat_id": "42"},
        lark=None,
    )
    cfg_path = tmp_path / "config.toml"
    cfg_path.write_text(toml)

    cfg = load_config(cfg_path)
    assert cfg.notifiers["telegram"]["bot_token"] == "LITERAL_TOKEN"
    assert cfg.notifiers["telegram"]["chat_id"] == "42"


def test_render_config_toml_with_lark(tmp_path):
    """Lark webhook round-trips correctly."""
    repo1 = str(tmp_path / "repo1")
    Path(repo1).mkdir()

    toml = render_config_toml(
        repos=[repo1],
        ai_provider="anthropic-api",
        notify_on="always",
        log_path=str(tmp_path / "sync.log"),
        telegram=None,
        lark={"webhook": "https://open.larksuite.com/hook/abc123"},
    )
    cfg_path = tmp_path / "config.toml"
    cfg_path.write_text(toml)

    cfg = load_config(cfg_path)
    assert cfg.notifiers["lark"]["webhook"] == "https://open.larksuite.com/hook/abc123"
    assert cfg.notifiers["lark"]["enabled"] is True


def test_render_config_toml_defaults_applied(tmp_path):
    """[defaults] fields propagate to repos via load_config."""
    repo1 = str(tmp_path / "repo1")
    Path(repo1).mkdir()

    toml = render_config_toml(
        repos=[repo1],
        ai_provider="rules",
        notify_on="change_or_fail",
        log_path=str(tmp_path / "sync.log"),
    )
    cfg_path = tmp_path / "config.toml"
    cfg_path.write_text(toml)

    cfg = load_config(cfg_path)
    r = cfg.repos[0]
    assert r.ai_provider == "rules"
    assert r.ai_staging is True
    assert r.ai_gitignore_autowrite is True
    assert r.push is True
    assert r.notify_on == "change_or_fail"


# ---------------------------------------------------------------------------
# CLI smoke test with --yes --no-schedule
# ---------------------------------------------------------------------------


def test_init_yes_no_schedule_writes_valid_config(tmp_path, monkeypatch):
    """git-auto-sync init --yes --no-schedule writes a config that load_config accepts.

    We monkeypatch scan_git_repos so we don't depend on the filesystem layout.
    """
    repo_dir = tmp_path / "myrepo"
    repo_dir.mkdir()
    subprocess.run(["git", "init", str(repo_dir)], check=True, capture_output=True)

    # Patch the default scan parent inside the wizard module
    import git_auto_sync.wizard as wizard_mod

    monkeypatch.setattr(
        wizard_mod,
        "scan_git_repos",
        lambda parent: [str(repo_dir.resolve())],
    )

    cfg_path = tmp_path / "config.toml"
    from git_auto_sync.cli import main

    rc = main(["init", "--yes", "--no-schedule", "--config", str(cfg_path)])
    assert rc == 0
    assert cfg_path.exists()

    cfg = load_config(cfg_path)
    assert len(cfg.repos) == 1
    assert cfg.repos[0].path == str(repo_dir.resolve())


def test_init_yes_always_backs_up_existing_config(tmp_path, monkeypatch):
    """--yes must still back up an existing config before overwriting it."""
    repo_dir = tmp_path / "myrepo"
    repo_dir.mkdir()
    subprocess.run(["git", "init", str(repo_dir)], check=True, capture_output=True)

    import git_auto_sync.wizard as wizard_mod

    monkeypatch.setattr(
        wizard_mod,
        "scan_git_repos",
        lambda parent: [str(repo_dir.resolve())],
    )

    cfg_path = tmp_path / "config.toml"
    original_content = "# hand-edited config\n"
    cfg_path.write_text(original_content, encoding="utf-8")

    from git_auto_sync.cli import main

    rc = main(["init", "--yes", "--no-schedule", "--config", str(cfg_path)])
    assert rc == 0

    bak_path = Path(str(cfg_path) + ".bak")
    assert bak_path.exists(), "backup file must be created even with --yes"
    assert bak_path.read_text(encoding="utf-8") == original_content


def test_init_accepts_manual_repo_paths_when_scan_finds_none(tmp_path, monkeypatch):
    """Interactive init still allows manual repo paths when scanning finds nothing."""
    manual_repo = tmp_path / "manual"
    manual_repo.mkdir()

    import builtins

    import git_auto_sync.wizard as wizard_mod

    monkeypatch.setattr(wizard_mod, "scan_git_repos", lambda parent: [])
    monkeypatch.setattr(wizard_mod.shutil, "which", lambda name: None)

    answers = iter(
        [
            str(tmp_path),  # parent directory to scan
            str(manual_repo),  # extra absolute repo path
            "",  # finish extra paths
            "rules",  # AI provider
            "",  # default notify_on
            "",  # default log path
            "n",  # no Telegram
            "n",  # no Lark
        ]
    )
    monkeypatch.setattr(builtins, "input", lambda prompt="": next(answers))

    cfg_path = tmp_path / "config.toml"
    from git_auto_sync.cli import main

    rc = main(["init", "--no-schedule", "--config", str(cfg_path)])
    assert rc == 0

    cfg = load_config(cfg_path)
    assert [repo.path for repo in cfg.repos] == [str(manual_repo.resolve())]


def test_init_accepts_tilde_path_when_scan_finds_none(tmp_path, monkeypatch):
    """Tilde-prefixed repo path is accepted as explicit path input."""
    manual_repo = tmp_path / "manual"
    manual_repo.mkdir()

    import builtins
    import os

    import git_auto_sync.wizard as wizard_mod

    monkeypatch.setattr(wizard_mod, "scan_git_repos", lambda parent: [])
    monkeypatch.setattr(wizard_mod.shutil, "which", lambda name: None)

    original_home = os.environ.get("HOME", "")
    original_user_profile = os.environ.get("USERPROFILE", "")
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))

    answers = iter(
        [
            str(tmp_path),
            "~/manual",
            "",
            "rules",
            "",
            "",
            "n",
            "n",
        ]
    )
    monkeypatch.setattr(builtins, "input", lambda prompt="": next(answers))

    cfg_path = tmp_path / "config_tilde.toml"
    from git_auto_sync.cli import main

    rc = main(["init", "--no-schedule", "--config", str(cfg_path)])
    assert rc == 0

    cfg = load_config(cfg_path)
    assert [repo.path for repo in cfg.repos] == [str(manual_repo.resolve())]

    if original_home:
        monkeypatch.setenv("HOME", original_home)
    else:
        monkeypatch.delenv("HOME", raising=False)
    if original_user_profile:
        monkeypatch.setenv("USERPROFILE", original_user_profile)
    else:
        monkeypatch.delenv("USERPROFILE", raising=False)


def test_resolve_repo_token_tilde_path_uses_explicit_lookup(tmp_path, monkeypatch):
    """A user-entered tilde path should never be treated as repository-name matching."""
    manual_repo = tmp_path / "entropy-nexus"
    manual_repo.mkdir()

    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))

    selected = _resolve_repo_token(
        "~/entropy-nexus",
        found=[str((tmp_path / "other-repo").resolve())],
        scan_parent=tmp_path,
    )
    assert selected == [str(manual_repo.resolve())]
