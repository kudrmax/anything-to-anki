from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from backend.domain.value_objects.app_version import AppVersion
from backend.infrastructure.adapters.release.file_installed_release import FileInstalledRelease

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = pytest.mark.unit

PNG_BYTES = b"\x89PNG-fake"


@pytest.fixture()
def project(tmp_path: Path) -> Path:
    (tmp_path / "pyproject.toml").write_text('[project]\nname = "x"\nversion = "2.3.4"\n')
    (tmp_path / "CHANGELOG.md").write_text("# Changelog\n")
    image_dir = tmp_path / "docs" / "images" / "changelog" / "2.3.4"
    image_dir.mkdir(parents=True)
    (image_dir / "shot.png").write_bytes(PNG_BYTES)
    (tmp_path / "docs" / "secret.txt").write_text("secret")
    return tmp_path


def test_reads_version_and_changelog(project: Path) -> None:
    release = FileInstalledRelease(project)

    assert release.version() == AppVersion(2, 3, 4)
    assert release.changelog_text() == "# Changelog\n"


def test_version_is_the_one_read_at_start(project: Path) -> None:
    release = FileInstalledRelease(project)

    (project / "pyproject.toml").write_text('[project]\nname = "x"\nversion = "9.9.9"\n')

    assert release.version() == AppVersion(2, 3, 4)


def test_serves_changelog_images(project: Path) -> None:
    assert FileInstalledRelease(project).asset("docs/images/changelog/2.3.4/shot.png") == PNG_BYTES


@pytest.mark.parametrize(
    "path",
    [
        "docs/secret.txt",
        "docs/images/changelog/../../secret.txt",
        "/etc/passwd",
        "docs/images/changelog/2.3.4/missing.png",
    ],
)
def test_other_paths_are_not_served(project: Path, path: str) -> None:
    assert FileInstalledRelease(project).asset(path) is None
