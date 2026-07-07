import pytest

from git_auto_sync.config import ConfigError, load_config
from git_auto_sync.models import RepoResult, RunSummary


def test_run_summary_flags():
    s = RunSummary(
        results=[
            RepoResult(path="/a", status="committed_pushed", message="feat: x"),
            RepoResult(path="/b", status="skipped"),
        ]
    )
    assert s.changed is True
    assert s.failed is False


def _write(tmp_path, text):
    p = tmp_path / "config.toml"
    p.write_text(text)
    return p


def test_repo_inherits_defaults_and_overrides(tmp_path):
    cfg = load_config(
        _write(
            tmp_path,
            """
[defaults]
push = true
ai_staging = true

[[repos]]
path = "~/foo"

[[repos]]
path = "/bar"
push = false
    """,
        )
    )
    foo, bar = cfg.repos
    assert foo.push is True and foo.ai_staging is True
    assert bar.push is False
    assert foo.path.replace("\\", "/").endswith("/foo")  # ~ expanded


def test_env_prefix_resolved(tmp_path, monkeypatch):
    monkeypatch.setenv("TG_TOKEN", "secret123")
    cfg = load_config(
        _write(
            tmp_path,
            """
[[repos]]
path = "/x"

[notifiers.telegram]
enabled = true
bot_token = "env:TG_TOKEN"
chat_id = "42"
""",
        )
    )
    assert cfg.notifiers["telegram"]["bot_token"] == "secret123"


def test_missing_env_raises(tmp_path):
    with pytest.raises(ConfigError):
        load_config(
            _write(
                tmp_path,
                """
[[repos]]
path = "/x"

[notifiers.telegram]
enabled = true
bot_token = "env:DOES_NOT_EXIST"
""",
            )
        )


def test_disabled_notifier_unset_env_does_not_break(tmp_path):
    # A disabled notifier with an unset env: placeholder must load fine.
    cfg = load_config(
        _write(
            tmp_path,
            """
[[repos]]
path = "/x"

[notifiers.telegram]
enabled = false
bot_token = "env:DEFINITELY_NOT_SET"
    """,
        )
    )
    assert all(r.path.replace("\\", "/").endswith("/x") for r in cfg.repos)
    # left unresolved since disabled
    assert cfg.notifiers["telegram"]["bot_token"] == "env:DEFINITELY_NOT_SET"


def test_no_repos_raises(tmp_path):
    with pytest.raises(ConfigError):
        load_config(_write(tmp_path, "[defaults]\npush = true\n"))


def test_missing_path_raises(tmp_path):
    with pytest.raises(ConfigError):
        load_config(
            _write(
                tmp_path,
                """
[[repos]]
branch = "main"
""",
            )
        )


def test_invalid_notify_on_raises(tmp_path):
    with pytest.raises(ConfigError):
        load_config(
            _write(
                tmp_path,
                """
[[repos]]
path = "/x"
notify_on = "sometimes"
""",
            )
        )


def test_invalid_ai_provider_raises(tmp_path):
    with pytest.raises(ConfigError):
        load_config(
            _write(
                tmp_path,
                """
[[repos]]
path = "/x"
ai_provider = "gpt"
""",
            )
        )


def test_home_work_tree_requires_allowlist_policy(tmp_path, monkeypatch):
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("USERPROFILE", str(home))

    with pytest.raises(ConfigError, match="user home directory"):
        load_config(
            _write(
                tmp_path,
                """
[[repos]]
path = "~/"
git_dir = "~/.homegit.git"
work_tree = "~/"
""",
            )
        )


def test_home_work_tree_accepts_allowlist_policy(tmp_path, monkeypatch):
    home = tmp_path / "home"
    home.mkdir()
    include = home / ".homegitinclude"
    include.write_text(".zshrc\n")
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("USERPROFILE", str(home))

    cfg = load_config(
        _write(
            tmp_path,
            """
[[repos]]
path = "~/"
git_dir = "~/.homegit.git"
work_tree = "~/"

[repos.path_policy]
mode = "allowlist"
include_file = "~/.homegitinclude"
""",
        )
    )

    repo = cfg.repos[0]
    assert repo.git_dir.replace("\\", "/").endswith("/home/.homegit.git")
    assert repo.work_tree == str(home.resolve())
    assert repo.path_policy.mode == "allowlist"
    assert repo.path_policy.include_file == str(include.resolve())


def test_git_dir_work_tree_requires_allowlist_policy(tmp_path):
    work = tmp_path / "work"
    git_dir = tmp_path / "repo.git"
    work.mkdir()
    git_dir.mkdir()

    with pytest.raises(ConfigError, match="git_dir/work_tree"):
        load_config(
            _write(
                tmp_path,
                f"""
[[repos]]
path = "{work.as_posix()}"
git_dir = "{git_dir.as_posix()}"
work_tree = "{work.as_posix()}"
""",
            )
        )
