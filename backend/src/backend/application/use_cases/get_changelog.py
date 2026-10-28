from __future__ import annotations

from typing import TYPE_CHECKING

from backend.application.dto.release_dtos import ChangelogEntryDTO
from backend.domain.exceptions import LongOperationInProgressError
from backend.domain.value_objects.app_version import AppVersion

if TYPE_CHECKING:
    from backend.domain.ports.installed_release import InstalledRelease
    from backend.domain.ports.settings_repository import SettingsRepository
    from backend.domain.ports.unit_of_work import UnitOfWork
    from backend.domain.services.changelog_parser import ChangelogParser

CHANGELOG_SEEN_VERSION_KEY = "changelog_seen_version"


class GetChangelogUseCase:
    """The changelog of the installed copy and what in it the user has not seen yet."""

    def __init__(
        self,
        installed: InstalledRelease,
        settings_repo: SettingsRepository,
        parser: ChangelogParser,
        unit_of_work: UnitOfWork,
    ) -> None:
        self._installed = installed
        self._settings_repo = settings_repo
        self._parser = parser
        self._unit_of_work = unit_of_work

    def all(self) -> list[ChangelogEntryDTO]:
        return [ChangelogEntryDTO.from_entry(entry) for entry in self._parser.parse(self._text())]

    def unseen(self) -> list[ChangelogEntryDTO]:
        current = self._installed.version()
        seen = self._seen_version()
        if seen is None:
            self._remember_fresh_install()
            return []
        return [
            ChangelogEntryDTO.from_entry(entry)
            for entry in self._parser.parse(self._text())
            if seen < entry.version <= current
        ]

    def mark_seen(self) -> None:
        with self._unit_of_work.write():
            self._settings_repo.set(CHANGELOG_SEEN_VERSION_KEY, str(self._installed.version()))

    def _remember_fresh_install(self) -> None:
        """Best-effort: while a long operation refuses writes the next call does it."""
        try:
            self.mark_seen()
        except LongOperationInProgressError:
            return

    def _text(self) -> str:
        return self._installed.changelog_text()

    def _seen_version(self) -> AppVersion | None:
        stored = self._settings_repo.get(CHANGELOG_SEEN_VERSION_KEY)
        if not stored:
            return None
        try:
            return AppVersion.parse(stored)
        except ValueError:
            return None
