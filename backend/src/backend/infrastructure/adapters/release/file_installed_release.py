from __future__ import annotations

import tomllib
from typing import TYPE_CHECKING

from backend.domain.ports.installed_release import InstalledRelease
from backend.domain.services.changelog_asset_path import is_changelog_asset_path
from backend.domain.value_objects.app_version import AppVersion

if TYPE_CHECKING:
    from pathlib import Path

PYPROJECT_FILE = "pyproject.toml"
CHANGELOG_FILE = "CHANGELOG.md"


class FileInstalledRelease(InstalledRelease):
    """The release checked out in the project folder. Its version is the one the server
    started with: a checkout under a running server does not change the code it runs."""

    def __init__(self, project_dir: Path) -> None:
        self._project_dir = project_dir
        with (project_dir / PYPROJECT_FILE).open("rb") as pyproject:
            self._version = AppVersion.parse(tomllib.load(pyproject)["project"]["version"])

    def version(self) -> AppVersion:
        return self._version

    def changelog_text(self) -> str:
        return (self._project_dir / CHANGELOG_FILE).read_text(encoding="utf-8")

    def asset(self, path: str) -> bytes | None:
        if not is_changelog_asset_path(path):
            return None
        file = self._project_dir / path
        return file.read_bytes() if file.is_file() else None
