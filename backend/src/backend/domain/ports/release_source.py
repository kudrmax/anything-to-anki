from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from backend.domain.value_objects.app_version import AppVersion


class ReleaseSource(ABC):
    """Port for published releases the installed copy has not got yet."""

    @abstractmethod
    def latest(self) -> AppVersion | None:
        """Fetches and returns the newest published version, or None if it cannot be learned."""

    @abstractmethod
    def changelog_text(self, version: AppVersion) -> str | None:
        """The CHANGELOG.md of that release, or None if it is unavailable."""

    @abstractmethod
    def asset(self, version: AppVersion, path: str) -> bytes | None:
        """A changelog image of that release, or None if it is missing or not allowed."""
