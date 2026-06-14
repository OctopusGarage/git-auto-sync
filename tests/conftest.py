import subprocess

import pytest


def _run(args, cwd):
    return subprocess.run(args, cwd=cwd, capture_output=True, text=True, check=True)


@pytest.fixture
def git_repo(tmp_path):
    """A working repo wired to a local bare 'origin' on branch main."""
    remote = tmp_path / "remote.git"
    remote.mkdir()
    _run(["git", "init", "--bare", "-b", "main", "."], remote)

    work = tmp_path / "work"
    work.mkdir()
    _run(["git", "init", "-b", "main", "."], work)
    _run(["git", "config", "user.email", "t@t.io"], work)
    _run(["git", "config", "user.name", "t"], work)
    _run(["git", "remote", "add", "origin", str(remote)], work)
    (work / "README.md").write_text("init\n")
    _run(["git", "add", "-A"], work)
    _run(["git", "commit", "-m", "init"], work)
    _run(["git", "push", "-u", "origin", "main"], work)
    return work
