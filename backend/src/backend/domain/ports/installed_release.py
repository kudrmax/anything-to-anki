from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from backend.domain.value_objects.app_version import AppVersion


class InstalledRelease(ABC):
    """Port for the release this copy is running: its version, changelog and images."""

    @abstractmethod
    def version(self) -> AppVersion:
        """The installed version."""

    @abstractmethod
    def changelog_text(self) -> str:
        """The installed CHANGELOG.md."""

    @abstractmethod
    def asset(self, path: str) -> bytes | None:
        """A changelog image by repository path, or None if it is missing or not allowed."""
