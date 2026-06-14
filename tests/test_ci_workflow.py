from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_ci_runs_linux_macos_and_windows():
    text = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")

    assert "ubuntu-latest" in text
    assert "macos-latest" in text
    assert "windows-latest" in text
    assert "uv run pytest" in text
    assert "uv run ruff check" in text


def test_ci_checks_platform_installers():
    text = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")

    assert "bash -n install.sh" in text
    assert "install.ps1" in text
