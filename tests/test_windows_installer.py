from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_windows_installer_has_supported_install_flow():
    text = (ROOT / "install.ps1").read_text(encoding="utf-8")

    assert "https://astral.sh/uv/install.ps1" in text
    assert "GIT_AUTO_SYNC_VERSION" in text
    assert "GIT_AUTO_SYNC_DIR" in text
    assert "archive/refs/tags/$Tag.zip" in text
    assert "Expand-Archive" in text
    assert "git-auto-sync.cmd" in text
    assert "config.toml" in text
    assert "Existing config found" in text
    assert "git-auto-sync init --yes" in text


def test_windows_installer_launcher_pins_uv_and_forwards_args():
    text = (ROOT / "install.ps1").read_text(encoding="utf-8")

    assert "$UvBin = (Get-Command uv" in text
    assert "GIT_AUTO_SYNC_UV" in text
    assert "run --project" in text
    assert "git-auto-sync %*" in text
