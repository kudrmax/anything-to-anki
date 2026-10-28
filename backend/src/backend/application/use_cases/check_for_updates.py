from __future__ import annotations

from datetime import datetime, timedelta
from typing import TYPE_CHECKING

from backend.application.dto.release_dtos import ChangelogEntryDTO, UpdateStatusDTO
from backend.domain.value_objects.app_version import AppVersion

if TYPE_CHECKING:
    from backend.domain.ports.clock import Clock
    from backend.domain.ports.installed_release import InstalledRelease
    from backend.domain.ports.release_source import ReleaseSource
    from backend.domain.ports.settings_repository import SettingsRepository
    from backend.domain.ports.unit_of_work import UnitOfWork
    from backend.domain.services.changelog_parser import ChangelogParser

UPDATE_CHECK_INTERVAL = timedelta(days=1)
UPDATE_CHECKED_AT_KEY = "update_checked_at"
UPDATE_LATEST_VERSION_KEY = "update_latest_version"


class CheckForUpdatesUseCase:
    """Tells whether a newer release exists. The releases are asked for at most once a day;
    `force` asks again."""

    def __init__(
        self,
        installed: InstalledRelease,
        source: ReleaseSource,
        settings_repo: SettingsRepository,
        clock: Clock,
        parser: ChangelogParser,
        unit_of_work: UnitOfWork,
    ) -> None:
        self._installed = installed
        self._source = source
        self._settings_repo = settings_repo
        self._clock = clock
        self._parser = parser
        self._unit_of_work = unit_of_work

    def execute(self, force: bool) -> UpdateStatusDTO:
        current = self._installed.version()
        if not force and self._cache_is_fresh():
            latest = self._cached_latest()
        else:
            latest = self._ask_source()
        failed = force and latest is None
        available = latest is not None and latest > current
        entries = self._entries_between(current, latest) if available and latest else []
        return UpdateStatusDTO(
            current=str(current),
            latest=str(latest) if latest else None,
            available=available,
            entries=entries,
            check_failed=failed,
        )

    def _cache_is_fresh(self) -> bool:
        checked_at = self._settings_repo.get(UPDATE_CHECKED_AT_KEY)
        if not checked_at:
            return False
        try:
            return self._clock.now() - datetime.fromisoformat(checked_at) < UPDATE_CHECK_INTERVAL
        except ValueError:
            return False

    def _cached_latest(self) -> AppVersion | None:
        stored = self._settings_repo.get(UPDATE_LATEST_VERSION_KEY)
        if not stored:
            return None
        try:
            return AppVersion.parse(stored)
        except ValueError:
            return None

    def _ask_source(self) -> AppVersion | None:
        latest = self._source.latest()
        with self._unit_of_work.write():
            self._settings_repo.set(UPDATE_CHECKED_AT_KEY, self._clock.now().isoformat())
            if latest is not None:
                self._settings_repo.set(UPDATE_LATEST_VERSION_KEY, str(latest))
        return latest if latest is not None else self._cached_latest()

    def _entries_between(self, current: AppVersion, latest: AppVersion) -> list[ChangelogEntryDTO]:
        text = self._source.changelog_text(latest)
        if text is None:
            return []
        return [
            ChangelogEntryDTO.from_entry(entry)
            for entry in self._parser.parse(text)
            if current < entry.version <= latest
        ]
