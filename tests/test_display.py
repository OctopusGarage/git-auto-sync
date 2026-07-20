from pathlib import Path

from git_auto_sync import display
from git_auto_sync.display import display_path


def test_display_path_prefers_home_environment(monkeypatch, tmp_path):
    configured_home = tmp_path / "configured-home"
    platform_home = tmp_path / "platform-home"
    repo = configured_home / "repo"
    repo.mkdir(parents=True)
    platform_home.mkdir()
    monkeypatch.setenv("HOME", str(configured_home))
    monkeypatch.setattr(display.Path, "home", staticmethod(lambda: Path(platform_home)))

    assert display_path(str(repo)) == "~/repo"
