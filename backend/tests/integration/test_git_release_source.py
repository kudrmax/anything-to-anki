from __future__ import annotations

import subprocess
from typing import TYPE_CHECKING

import pytest
from backend.domain.value_objects.app_version import AppVersion
from backend.infrastructure.adapters.release.git_release_source import GitReleaseSource

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = pytest.mark.integration

PNG_BYTES = b"\x89PNG-fake"
IMAGE_PATH = "docs/images/changelog/1.1.0/shot.png"
IDENTITY = ["-c", "user.name=Test", "-c", "user.email=test@example.com"]


def git(cwd: Path, *args: str) -> None:
    subprocess.run(["git", *IDENTITY, *args], cwd=cwd, check=True, capture_output=True)


def release(clone: Path, tag: str, changelog: str, *, with_image: bool = False) -> None:
    (clone / "CHANGELOG.md").write_text(changelog)
    (clone / "notes.txt").write_text(tag)
    if with_image:
        (clone / IMAGE_PATH).parent.mkdir(parents=True, exist_ok=True)
        (clone / IMAGE_PATH).write_bytes(PNG_BYTES)
    git(clone, "add", "-A")
    git(clone, "commit", "-m", tag)
    git(clone, "tag", tag)


@pytest.fixture()
def publisher(tmp_path: Path) -> Path:
    bare = tmp_path / "origin.git"
    git(tmp_path, "init", "--bare", str(bare))
    clone = tmp_path / "publisher"
    git(tmp_path, "clone", str(bare), str(clone))
    release(clone, "v1.0.0", "first")
    release(clone, "v1.1.0", "second", with_image=True)
    git(clone, "tag", "not-a-release")
    git(clone, "push", "origin", "HEAD", "--tags")
    return clone


@pytest.fixture()
def installed(tmp_path: Path, publisher: Path) -> Path:
    bare = tmp_path / "origin.git"
    installed = tmp_path / "installed"
    git(tmp_path, "clone", "--no-tags", str(bare), str(installed))
    return installed


def test_latest_fetches_and_picks_highest_tag(installed: Path) -> None:
    assert GitReleaseSource(installed).latest() == AppVersion(1, 1, 0)


def test_changelog_text_of_a_version(installed: Path) -> None:
    source = GitReleaseSource(installed)
    source.latest()

    assert source.changelog_text(AppVersion(1, 1, 0)) == "second"
    assert source.changelog_text(AppVersion(1, 0, 0)) == "first"
    assert source.changelog_text(AppVersion(9, 9, 9)) is None


def test_asset_of_a_version(installed: Path) -> None:
    source = GitReleaseSource(installed)
    source.latest()

    assert source.asset(AppVersion(1, 1, 0), IMAGE_PATH) == PNG_BYTES
    assert source.asset(AppVersion(1, 0, 0), IMAGE_PATH) is None


@pytest.mark.parametrize("path", ["notes.txt", "docs/images/changelog/../../../notes.txt"])
def test_asset_outside_changelog_images_is_not_served(installed: Path, path: str) -> None:
    source = GitReleaseSource(installed)
    source.latest()

    assert source.asset(AppVersion(1, 1, 0), path) is None


def test_latest_is_none_without_origin(tmp_path: Path) -> None:
    lonely = tmp_path / "lonely"
    git(tmp_path, "init", str(lonely))

    assert GitReleaseSource(lonely).latest() is None


def test_changelog_that_is_not_utf8_is_unavailable(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    git(tmp_path, "init", str(repo))
    (repo / "CHANGELOG.md").write_bytes(b"\xff\xfe not utf-8")
    git(repo, "add", "-A")
    git(repo, "commit", "-m", "v1.0.0")
    git(repo, "tag", "v1.0.0")

    assert GitReleaseSource(repo).changelog_text(AppVersion(1, 0, 0)) is None
