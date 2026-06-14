from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

pytestmark = pytest.mark.skipif(os.name == "nt", reason="install.sh is POSIX-only")

ROOT = Path(__file__).resolve().parents[1]
INSTALL_SH = ROOT / "install.sh"


def _write_executable(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")
    path.chmod(0o755)


def _fake_installer_env(tmp_path: Path) -> tuple[dict[str, str], Path, Path]:
    home = tmp_path / "home"
    fakebin = tmp_path / "fakebin"
    home.mkdir()
    fakebin.mkdir()
    uv_log = tmp_path / "uv.log"

    _write_executable(
        fakebin / "uv",
        """#!/bin/bash
{
  echo "---"
  echo "PATH=$PATH"
  echo "ARGS=$*"
} >> "$UV_LOG"
exit 0
""",
    )
    _write_executable(
        fakebin / "curl",
        """#!/bin/bash
out=""
while [ "$#" -gt 0 ]; do
  if [ "$1" = "-o" ]; then
    shift
    out="$1"
  fi
  shift || true
done
if [ -n "$out" ]; then
  : > "$out"
fi
exit 0
""",
    )
    _write_executable(
        fakebin / "tar",
        """#!/bin/bash
exit 0
""",
    )

    env = os.environ.copy()
    env.update({
        "HOME": str(home),
        "PATH": f"{fakebin}:{env.get('PATH', '')}",
        "GIT_AUTO_SYNC_VERSION": "v9.9.9",
        "UV_LOG": str(uv_log),
    })
    env.pop("GIT_AUTO_SYNC_DIR", None)
    return env, home, uv_log


def _run_install(tmp_path: Path, env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["bash", str(INSTALL_SH)],
        cwd=tmp_path,
        env=env,
        input="",
        capture_output=True,
        text=True,
        check=False,
    )


def test_installer_preserves_existing_config_and_skips_init(tmp_path):
    env, home, uv_log = _fake_installer_env(tmp_path)
    config_path = home / ".git-auto-sync" / "config.toml"
    config_path.parent.mkdir(parents=True)
    original_config = "# user config\n[[repos]]\npath = \"/repo\"\n"
    config_path.write_text(original_config, encoding="utf-8")

    result = _run_install(tmp_path, env)

    assert result.returncode == 0, result.stdout + result.stderr
    assert config_path.read_text(encoding="utf-8") == original_config
    assert "git-auto-sync init" not in uv_log.read_text(encoding="utf-8")
    assert "Existing config found" in result.stdout


def test_installer_launcher_uses_resolved_uv_path(tmp_path):
    env, home, _uv_log = _fake_installer_env(tmp_path)
    config_path = home / ".git-auto-sync" / "config.toml"
    config_path.parent.mkdir(parents=True)
    config_path.write_text("[[repos]]\npath = \"/repo\"\n", encoding="utf-8")

    result = _run_install(tmp_path, env)

    assert result.returncode == 0, result.stdout + result.stderr
    launcher = home / ".local" / "bin" / "git-auto-sync"
    text = launcher.read_text(encoding="utf-8")
    assert f'exec "{tmp_path / "fakebin" / "uv"}" run' in text
    assert "exec uv run" not in text
    assert "GIT_AUTO_SYNC_UV" in text


def test_installer_exports_launcher_dir_before_running_init(tmp_path):
    env, home, uv_log = _fake_installer_env(tmp_path)

    result = _run_install(tmp_path, env)

    assert result.returncode == 0, result.stdout + result.stderr
    entries = uv_log.read_text(encoding="utf-8").split("---\n")
    init_entry = next(entry for entry in entries if "git-auto-sync init --yes" in entry)
    path_line = next(line for line in init_entry.splitlines() if line.startswith("PATH="))
    assert str(home / ".local" / "bin") in path_line.split("=", 1)[1].split(":")
