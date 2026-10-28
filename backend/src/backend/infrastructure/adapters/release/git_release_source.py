from __future__ import annotations

import logging
import subprocess
from typing import TYPE_CHECKING

from backend.domain.ports.release_source import ReleaseSource
from backend.domain.services.changelog_asset_path import is_changelog_asset_path
from backend.domain.value_objects.app_version import AppVersion

if TYPE_CHECKING:
    from pathlib import Path

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT_S = 20
TAG_PATTERN = "v*"
CHANGELOG_FILE = "CHANGELOG.md"


class GitReleaseSource(ReleaseSource):
    """Releases are the `v*` tags of the project folder's git remote."""

    def __init__(self, project_dir: Path, timeout_s: float = DEFAULT_TIMEOUT_S) -> None:
        self._project_dir = project_dir
        self._timeout_s = timeout_s

    def latest(self) -> AppVersion | None:
        try:
            self._git("fetch", "--tags", "--quiet", "origin")
            tags = self._git("tag", "--list", TAG_PATTERN).decode().split()
        except (subprocess.SubprocessError, OSError) as error:
            logger.warning("Could not learn the latest release: %s", error)
            return None
        versions = [version for tag in tags if (version := self._parse_tag(tag)) is not None]
        return max(versions, default=None)

    def changelog_text(self, version: AppVersion) -> str | None:
        content = self._show(version, CHANGELOG_FILE)
        if content is None:
            return None
        try:
            return content.decode("utf-8")
        except UnicodeDecodeError:
            logger.warning("The changelog of release %s is not UTF-8", version)
            return None

    def asset(self, version: AppVersion, path: str) -> bytes | None:
        return self._show(version, path) if is_changelog_asset_path(path) else None

    def _show(self, version: AppVersion, path: str) -> bytes | None:
        try:
            return self._git("show", f"v{version}:{path}")
        except (subprocess.SubprocessError, OSError) as error:
            logger.warning("Could not read %s of release %s: %s", path, version, error)
            return None

    def _git(self, *args: str) -> bytes:
        completed = subprocess.run(
            ["git", *args],
            cwd=self._project_dir,
            capture_output=True,
            check=True,
            timeout=self._timeout_s,
        )
        return completed.stdout

    @staticmethod
    def _parse_tag(tag: str) -> AppVersion | None:
        try:
            return AppVersion.parse(tag)
        except ValueError:
            return None
