from pathlib import Path

from git_auto_sync import git_ops


def test_has_changes_detects_untracked_and_clean(git_repo):
    assert git_ops.has_changes(git_repo) is False
    (Path(git_repo) / "new.txt").write_text("hi\n")
    assert git_ops.has_changes(git_repo) is True


def test_list_changes_reports_status(git_repo):
    (Path(git_repo) / "new.txt").write_text("hi\n")
    (Path(git_repo) / "README.md").write_text("changed\n")
    changes = {c.path: c.status for c in git_ops.list_changes(git_repo)}
    assert changes["new.txt"] == "A"
    assert changes["README.md"] == "M"


def test_current_branch(git_repo):
    assert git_ops.current_branch(git_repo) == "main"


def test_commit_paths_and_push(git_repo):
    (Path(git_repo) / "new.txt").write_text("hi\n")
    git_ops.add_paths(git_repo, ["new.txt"])
    git_ops.commit(git_repo, "feat: add new")
    assert git_ops.has_changes(git_repo) is False
    ok, err = git_ops.pull_rebase(git_repo)
    assert ok is True, err
    ok, err = git_ops.push(git_repo)
    assert ok is True, err


def test_commit_falls_back_to_unsigned_when_signing_fails(git_repo):
    import subprocess
    # Force signing on but point gpg at a missing binary so signing fails the
    # same way it does in a headless run (gpg not found / cannot sign).
    subprocess.run(["git", "config", "commit.gpgsign", "true"], cwd=git_repo, check=True)
    subprocess.run(["git", "config", "gpg.program", "/nonexistent/gpg"], cwd=git_repo, check=True)
    (Path(git_repo) / "new.txt").write_text("hi\n")
    git_ops.add_paths(git_repo, ["new.txt"])
    ok, err = git_ops.commit(git_repo, "feat: add new")
    assert ok is True, err
    assert git_ops.has_changes(git_repo) is False


def test_pull_rebase_conflict_aborts_clean(git_repo, tmp_path):
    # Create a divergent commit on the remote via a second clone.
    import subprocess
    clone = tmp_path / "clone"
    subprocess.run(["git", "clone", str(Path(git_repo).parent / "remote.git"), str(clone)],
                   check=True, capture_output=True, text=True)
    subprocess.run(["git", "config", "user.email", "t@t.io"], cwd=clone, check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=clone, check=True)
    (clone / "README.md").write_text("remote-change\n")
    subprocess.run(["git", "commit", "-am", "remote"], cwd=clone, check=True,
                   capture_output=True, text=True)
    subprocess.run(["git", "push"], cwd=clone, check=True, capture_output=True, text=True)

    # Local conflicting commit on the same line.
    (Path(git_repo) / "README.md").write_text("local-change\n")
    git_ops.add_paths(git_repo, ["README.md"])
    git_ops.commit(git_repo, "chore: local")
    ok, err = git_ops.pull_rebase(git_repo)
    assert ok is False
    # Repo must be left clean (rebase aborted), not mid-rebase.
    assert git_ops.has_changes(git_repo) is False
    assert not (Path(git_repo) / ".git" / "rebase-merge").exists()


def test_list_changes_handles_quoted_rename(git_repo):
    import subprocess
    old = Path(git_repo) / "old name.txt"
    old.write_text("data\n")
    subprocess.run(["git", "add", "-A"], cwd=git_repo, check=True,
                   capture_output=True, text=True)
    subprocess.run(["git", "commit", "-m", "add spaced file"], cwd=git_repo, check=True,
                   capture_output=True, text=True)
    subprocess.run(["git", "mv", "old name.txt", "new name.txt"], cwd=git_repo, check=True,
                   capture_output=True, text=True)
    changes = {c.path: c.status for c in git_ops.list_changes(git_repo)}
    assert "new name.txt" in changes
    assert changes["new name.txt"] == "R"
    # no corrupted key with a stray quote
    assert not any('"' in p for p in changes)
