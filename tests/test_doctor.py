from git_auto_sync.config import Config
from git_auto_sync.doctor import check_runtime_tools, required_tools_for_repo
from git_auto_sync.models import RepoConfig


def test_required_tools_for_repo_detects_git_lfs_from_config(tmp_path):
    repo = tmp_path / "repo"
    hooks = repo / ".git" / "hooks"
    hooks.mkdir(parents=True)
    (repo / ".git" / "config").write_text(
        "[lfs]\n\trepositoryformatversion = 0\n", encoding="utf-8"
    )

    assert required_tools_for_repo(repo) == {"git-lfs"}


def test_required_tools_for_repo_detects_git_crypt_from_attributes(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / ".gitattributes").write_text(
        "secrets/** filter=git-crypt diff=git-crypt\n", encoding="utf-8"
    )

    assert required_tools_for_repo(repo) == {"git-crypt"}


def test_check_runtime_tools_reports_missing_required_tools(tmp_path):
    repo = tmp_path / "repo"
    empty_bin = tmp_path / "empty-bin"
    empty_bin.mkdir()
    (repo / ".git").mkdir(parents=True)
    (repo / ".git" / "config").write_text(
        "[lfs]\n\trepositoryformatversion = 0\n", encoding="utf-8"
    )
    config = Config(
        repos=[RepoConfig(path=str(repo), push=True)],
        notifiers={},
    )

    results = check_runtime_tools(config, search_path=str(empty_bin))

    assert len(results) == 1
    assert results[0].ok is False
    assert results[0].tool == "git-lfs"
    assert results[0].repo == str(repo)
    assert str(empty_bin) in results[0].message


def test_check_runtime_tools_skips_repos_that_do_not_push(tmp_path):
    repo = tmp_path / "repo"
    (repo / ".git").mkdir(parents=True)
    (repo / ".git" / "config").write_text(
        "[lfs]\n\trepositoryformatversion = 0\n", encoding="utf-8"
    )
    config = Config(
        repos=[RepoConfig(path=str(repo), push=False)],
        notifiers={},
    )

    assert check_runtime_tools(config, search_path="/usr/bin:/bin") == []
