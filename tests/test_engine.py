import subprocess
from pathlib import Path

from git_auto_sync.engine import append_gitignore, run_sync, should_notify, sync_repo
from git_auto_sync.models import PathPolicyConfig, RepoConfig, RepoResult, RunSummary
from git_auto_sync.providers.rules import RulesProvider


def _repo_config(path, **kw):
    return RepoConfig(path=str(path), **kw)


def test_skipped_when_no_changes(git_repo):
    cfg = _repo_config(git_repo)
    result = sync_repo(cfg, RulesProvider())
    assert result.status == "skipped"


def test_commit_and_push(git_repo):
    (Path(git_repo) / "feature.py").write_text("print('x')\n")
    cfg = _repo_config(git_repo, ai_staging=False)  # add -A path
    result = sync_repo(cfg, RulesProvider())
    assert result.status == "committed_pushed"
    assert result.message


def test_normal_repo_without_path_policy_preserves_add_all_behavior(git_repo):
    (Path(git_repo) / ".env").write_text("SECRET=1\n")
    cfg = _repo_config(git_repo, ai_staging=False, push=False)

    result = sync_repo(cfg, RulesProvider())

    assert result.status == "committed"
    tracked = subprocess.run(
        ["git", "ls-files"],
        cwd=git_repo,
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    assert ".env" in tracked


def test_bare_work_tree_sync_stages_only_allowlist(tmp_path):
    git_dir = tmp_path / "config.git"
    work_tree = tmp_path / "home"
    include = tmp_path / "include"
    work_tree.mkdir()
    include.write_text(".zshrc\n")
    subprocess.run(["git", "init", "--bare", "-b", "main", str(git_dir)], check=True)
    subprocess.run(
        [
            "git",
            "--git-dir",
            str(git_dir),
            "--work-tree",
            str(work_tree),
            "config",
            "user.email",
            "t@t.io",
        ],
        check=True,
    )
    subprocess.run(
        [
            "git",
            "--git-dir",
            str(git_dir),
            "--work-tree",
            str(work_tree),
            "config",
            "user.name",
            "t",
        ],
        check=True,
    )

    (work_tree / ".zshrc").write_text("alias ll='ls -la'\n")
    (work_tree / ".ssh").mkdir()
    (work_tree / ".ssh" / "config").write_text("Host *\n")
    cfg = RepoConfig(
        path=str(work_tree),
        git_dir=str(git_dir),
        work_tree=str(work_tree),
        ai_staging=False,
        push=False,
        path_policy=PathPolicyConfig(mode="allowlist", include_file=str(include)),
    )

    result = sync_repo(cfg, RulesProvider())

    assert result.status == "committed"
    assert result.ignored_paths == []
    tracked = subprocess.run(
        ["git", "--git-dir", str(git_dir), "--work-tree", str(work_tree), "ls-files"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.splitlines()
    assert tracked == [".zshrc"]


def test_secret_excluded_and_gitignored(git_repo):
    (Path(git_repo) / "app.py").write_text("ok\n")
    (Path(git_repo) / ".env").write_text("SECRET=1\n")
    cfg = _repo_config(git_repo, ai_staging=True, ai_gitignore_autowrite=True, push=False)
    result = sync_repo(cfg, RulesProvider())
    assert result.status == "committed"
    assert ".env" in result.ignored_paths
    gitignore = (Path(git_repo) / ".gitignore").read_text()
    assert ".env" in gitignore
    # .env must not be committed.
    import subprocess

    tracked = subprocess.run(
        ["git", "ls-files"], cwd=git_repo, capture_output=True, text=True
    ).stdout
    assert ".env" not in tracked


def test_append_gitignore_dedupes(tmp_path):
    gi = tmp_path / ".gitignore"
    gi.write_text("*.log\n")
    append_gitignore(tmp_path, ["*.log", "secret.key"])
    content = gi.read_text()
    assert content.count("*.log") == 1
    assert "secret.key" in content


def test_run_sync_isolates_failing_repo(git_repo):
    # First repo's path does not exist, so git_ops raises inside sync_repo;
    # run_sync must record it as "failed" and still sync the second repo.
    (Path(git_repo) / "feature.py").write_text("print('x')\n")
    bad = RepoConfig(path="/nonexistent/repo", ai_provider="rules")
    good = RepoConfig(path=str(git_repo), ai_provider="rules", ai_staging=False)

    summary = run_sync([bad, good], lambda name: RulesProvider())
    assert len(summary.results) == 2
    assert summary.results[0].status == "failed"
    assert summary.results[1].status == "committed_pushed"


def test_should_notify_policies():
    changed = RunSummary(results=[RepoResult(path="/a", status="committed_pushed")])
    failed = RunSummary(results=[RepoResult(path="/a", status="failed")])
    quiet = RunSummary(results=[RepoResult(path="/a", status="skipped")])
    assert should_notify("change_or_fail", changed) is True
    assert should_notify("change_or_fail", quiet) is False
    assert should_notify("fail_only", changed) is False
    assert should_notify("fail_only", failed) is True
    assert should_notify("always", quiet) is True
