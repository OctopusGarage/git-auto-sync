"""Release helpers for the self-update command."""

from __future__ import annotations

import os
import shutil
import tarfile
import tempfile
import urllib.request
import zipfile
from pathlib import Path, PurePosixPath

REPO = "OctopusGarage/git-auto-sync"
PROJECT_DIR = Path(__file__).resolve().parent.parent
RELEASE_ARTIFACT_TEMPLATE = "git-auto-sync-{tag}-release.tar.gz"


# ---------------------------------------------------------------------------
# Pure helpers (unit-tested)
# ---------------------------------------------------------------------------


def version_tuple(v: str) -> tuple[int, ...]:
    """Parse 'v0.1.0' or '0.1.0' -> (0, 1, 0).

    Strips a leading 'v', then splits on '.'.  Truncates at the first
    component that isn't a plain integer so pre-release suffixes are tolerated.
    """
    v = v.lstrip("v")
    parts: list[int] = []
    for part in v.split("."):
        if part.isdigit():
            parts.append(int(part))
        else:
            break
    return tuple(parts)


def is_newer(candidate: str, current: str) -> bool:
    """Return True if *candidate* is strictly newer than *current*."""
    return version_tuple(candidate) > version_tuple(current)


def tag_from_url(url: str) -> str:
    """Return the last path segment of a GitHub releases URL.

    Works for both '.../releases/tag/v0.3.1' and a redirected
    '.../releases/latest' URL.
    """
    return url.rstrip("/").rsplit("/", 1)[-1]


def installed_version() -> str | None:
    """Return the currently installed package version string."""
    try:
        import git_auto_sync

        return git_auto_sync.__version__
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Side-effecting operations
# ---------------------------------------------------------------------------


def resolve_latest_tag() -> str | None:
    """Follow the /releases/latest redirect and return the tag (e.g. 'v0.2.0').

    Returns None on any network error or if the resolved URL doesn't look like
    a versioned tag.
    """
    try:
        with urllib.request.urlopen(f"https://github.com/{REPO}/releases/latest", timeout=20) as r:
            final_url = r.geturl() if hasattr(r, "geturl") else r.url
        tag = tag_from_url(final_url)
        return tag if tag.startswith("v") else None
    except Exception:
        return None


def _download_to(url: str, dest: str | Path) -> None:
    urllib.request.urlretrieve(url, dest)


def _extract_zip_strip_root(zip_path: str | Path, dest: str | Path) -> None:
    dest = Path(dest)
    dest.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path) as zf:
        for info in zf.infolist():
            parts = PurePosixPath(info.filename).parts
            if len(parts) <= 1:
                continue
            relative = Path(*parts[1:])
            if any(part in {"", ".."} for part in relative.parts):
                continue
            target = dest / relative
            if info.is_dir():
                target.mkdir(parents=True, exist_ok=True)
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            with zf.open(info) as src, target.open("wb") as out:
                shutil.copyfileobj(src, out)


def _extract_tar_strip_root(tar_path: str | Path, dest: str | Path) -> None:
    dest = Path(dest)
    dest.mkdir(parents=True, exist_ok=True)
    with tarfile.open(tar_path, "r:gz") as tf:
        for member in tf.getmembers():
            if not member.name:
                continue
            parts = member.name.split("/")
            if len(parts) < 2:
                continue
            member.name = "/".join(parts[1:])
            if member.name.startswith("..") or "/../" in member.name:
                continue
            if not member.name:
                continue
            tf.extract(member, dest)


def _release_artifact_url(tag: str) -> str:
    return f"https://github.com/{REPO}/releases/download/{tag}/{RELEASE_ARTIFACT_TEMPLATE.format(tag=tag)}"


def download_release(tag: str, dest: str | Path) -> bool:
    """Download release artifact for *tag* and extract it into *dest*.

    Prefers the minimal packaged release archive. If that is unavailable,
    falls back to the tag source archive.
    """
    tmp = tempfile.mkdtemp()
    archive: str | None = None
    use_tar = False

    # Prefer the minimal release bundle published to GitHub Releases.
    try:
        archive = os.path.join(tmp, "release.tar.gz")
        _download_to(_release_artifact_url(tag), archive)
        use_tar = True
    except Exception:
        try:
            archive = os.path.join(tmp, "release.zip")
            fallback_url = f"https://github.com/{REPO}/archive/refs/tags/{tag}.zip"
            _download_to(fallback_url, archive)
            use_tar = False
        except Exception:
            return False

    try:
        if archive is None:
            return False
        if use_tar:
            _extract_tar_strip_root(archive, dest)
        else:
            _extract_zip_strip_root(archive, dest)
        return True
    except Exception:
        return False
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
