from __future__ import annotations

from pathlib import PurePosixPath

CHANGELOG_IMAGES_DIR = PurePosixPath("docs/images/changelog")
PARENT_SEGMENT = ".."


def is_changelog_asset_path(path: str) -> bool:
    """Only files under the changelog images folder may leave a release."""
    candidate = PurePosixPath(path)
    return (
        not candidate.is_absolute()
        and PARENT_SEGMENT not in candidate.parts
        and candidate.is_relative_to(CHANGELOG_IMAGES_DIR)
        and candidate != CHANGELOG_IMAGES_DIR
    )
