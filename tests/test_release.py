"""Tests for git_auto_sync.release — pure helpers only (no network)."""

from __future__ import annotations

import io
import shutil
import subprocess
import tarfile
from types import SimpleNamespace

import git_auto_sync
from git_auto_sync import cli, release

# ---------------------------------------------------------------------------
# version_tuple
# ---------------------------------------------------------------------------


def test_version_tuple_with_v_prefix():
    assert release.version_tuple("v1.2.3") == (1, 2, 3)


def test_version_tuple_without_prefix():
    assert release.version_tuple("0.1.0") == (0, 1, 0)


def test_version_tuple_truncates_non_numeric():
    # e.g. "1.2.3a" — truncate at the first non-int component
    assert release.version_tuple("1.2.3a") == (1, 2)


# ---------------------------------------------------------------------------
# is_newer
# ---------------------------------------------------------------------------


def test_is_newer_true():
    assert release.is_newer("v0.2.0", "0.1.0") is True


def test_is_newer_same_version():
    assert release.is_newer("v0.1.0", "0.1.0") is False


def test_is_newer_older():
    assert release.is_newer("v0.1.0", "0.2.0") is False


# ---------------------------------------------------------------------------
# tag_from_url
# ---------------------------------------------------------------------------


def test_tag_from_url_explicit_tag():
    url = "https://github.com/OctopusGarage/git-auto-sync/releases/tag/v0.3.1"
    assert release.tag_from_url(url) == "v0.3.1"


def test_tag_from_url_trailing_slash():
    url = "https://github.com/OctopusGarage/git-auto-sync/releases/tag/v0.3.1/"
    assert release.tag_from_url(url) == "v0.3.1"


# ---------------------------------------------------------------------------
# installed_version
# ---------------------------------------------------------------------------


def test_installed_version_matches_package():
    assert release.installed_version() == git_auto_sync.__version__


# ---------------------------------------------------------------------------
# --check CLI integration (monkeypatched, no network)
# ---------------------------------------------------------------------------


def test_cmd_update_check(monkeypatch, capsys):
    """--check should report installed vs available and return 0."""
    monkeypatch.setattr(release, "resolve_latest_tag", lambda: "v0.9.0")

    from git_auto_sync.cli import main

    rc = main(["update", "--check"])
    assert rc == 0

    out = capsys.readouterr().out
    assert git_auto_sync.__version__ in out
    assert "v0.9.0" in out


def test_cmd_update_uses_launcher_pinned_uv(monkeypatch, tmp_path):
    monkeypatch.setenv("GIT_AUTO_SYNC_UV", "/opt/uv/bin/uv")
    monkeypatch.setattr(release, "PROJECT_DIR", tmp_path)
    monkeypatch.setattr(release, "installed_version", lambda: "0.1.0")
    monkeypatch.setattr(release, "download_release", lambda tag, dest: True)

    calls = []
    monkeypatch.setattr(
        cli.subprocess,
        "run",
        lambda args, cwd, check: calls.append((args, cwd, check))
        or SimpleNamespace(returncode=0),
    )

    rc = cli.main(["update", "--version", "v0.9.0"])

    assert rc == 0
    assert calls == [(["/opt/uv/bin/uv", "sync"], tmp_path, False)]


def test_resolve_latest_tag_uses_python_url_response(monkeypatch):
    class Response:
        url = "https://github.com/OctopusGarage/git-auto-sync/releases/tag/v0.3.1"

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

    monkeypatch.setattr(
        release.urllib.request,
        "urlopen",
        lambda url, timeout: Response(),
    )

    assert release.resolve_latest_tag() == "v0.3.1"


def test_download_release_extracts_tar_without_external_commands(tmp_path, monkeypatch):
    src_archive = tmp_path / "release.tar.gz"
    with tarfile.open(src_archive, "w:gz") as tf:
        project_toml = tarfile.TarInfo("git-auto-sync-1.2.3/pyproject.toml")
        project_toml_data = b"[project]\n"
        project_toml.size = len(project_toml_data)
        tf.addfile(project_toml, fileobj=io.BytesIO(project_toml_data))

        init_toml = tarfile.TarInfo("git-auto-sync-1.2.3/git_auto_sync/__init__.py")
        init_toml_data = b"__version__ = '1.2.3'\n"
        init_toml.size = len(init_toml_data)
        tf.addfile(init_toml, fileobj=io.BytesIO(init_toml_data))

    downloaded_urls = []

    def fake_download(url, dest):
        downloaded_urls.append(url)
        shutil.copy2(src_archive, dest)

    monkeypatch.setattr(release, "_download_to", fake_download)
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("download_release must not shell out")
        ),
    )

    dest = tmp_path / "dest"
    dest.mkdir()
    config = dest / "config.toml"
    config.write_text("keep me\n", encoding="utf-8")

    assert release.download_release("v1.2.3", dest) is True
    assert downloaded_urls == [
        "https://github.com/OctopusGarage/git-auto-sync/releases/download/v1.2.3/git-auto-sync-v1.2.3-release.tar.gz"
    ]
    assert (dest / "pyproject.toml").read_text(encoding="utf-8") == "[project]\n"
    assert (dest / "git_auto_sync" / "__init__.py").read_text(
        encoding="utf-8"
    ) == "__version__ = '1.2.3'\n"
    assert config.read_text(encoding="utf-8") == "keep me\n"
