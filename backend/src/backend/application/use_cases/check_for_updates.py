from __future__ import annotations

from datetime import datetime, timedelta
from typing import TYPE_CHECKING

from backend.application.dto.release_dtos import ChangelogEntryDTO, UpdateStatusDTO
from backend.domain.exceptions import LongOperationInProgressError
from backend.domain.value_objects.app_version import AppVersion

if TYPE_CHECKING:
    from backend.domain.ports.clock import Clock
    from backend.domain.ports.installed_release import InstalledRelease
    from backend.domain.ports.release_source import ReleaseSource
    from backend.domain.ports.settings_repository import SettingsRepository
    from backend.domain.ports.unit_of_work import UnitOfWork
    from backend.domain.ports.update_runner import UpdateRunner
    from backend.domain.services.changelog_parser import ChangelogParser

UPDATE_CHECK_INTERVAL = timedelta(days=1)
# Offline, every page load would wait on a fetch that fails; this spaces the attempts out.
UPDATE_RETRY_INTERVAL = timedelta(hours=1)
UPDATE_CHECKED_AT_KEY = "update_checked_at"
UPDATE_RETRY_AT_KEY = "update_retry_at"
UPDATE_LATEST_VERSION_KEY = "update_latest_version"


class CheckForUpdatesUseCase:
    """Tells whether a newer release exists. The releases are asked for at most once a day,
    and a failed ask is tried again within the hour; `force` asks again."""

    def __init__(
        self,
        installed: InstalledRelease,
        source: ReleaseSource,
        settings_repo: SettingsRepository,
        clock: Clock,
        parser: ChangelogParser,
        unit_of_work: UnitOfWork,
        runner: UpdateRunner,
    ) -> None:
        self._installed = installed
        self._source = source
        self._settings_repo = settings_repo
        self._clock = clock
        self._parser = parser
        self._unit_of_work = unit_of_work
        self._runner = runner

    def execute(self, force: bool) -> UpdateStatusDTO:
        current = self._installed.version()
        fetch_failed = False
        if not force and (self._cache_is_fresh() or self._retry_is_pending()):
            latest = self._cached_latest()
        else:
            fetched = self._source.latest()
            fetch_failed = fetched is None
            self._remember(fetched)
            latest = fetched if fetched is not None else self._cached_latest()
        available = latest is not None and latest > current
        entries = self._entries_between(current, latest) if available and latest else []
        return UpdateStatusDTO(
            current=str(current),
            latest=str(latest) if latest else None,
            available=available,
            entries=entries,
            check_failed=force and fetch_failed,
            restart_command=self._runner.restart_command(),
            update_command=self._runner.update_command(),
        )

    def _cache_is_fresh(self) -> bool:
        checked_at = self._stored_time(UPDATE_CHECKED_AT_KEY)
        return checked_at is not None and self._clock.now() - checked_at < UPDATE_CHECK_INTERVAL

    def _retry_is_pending(self) -> bool:
        retry_at = self._stored_time(UPDATE_RETRY_AT_KEY)
        return retry_at is not None and self._clock.now() < retry_at

    def _stored_time(self, key: str) -> datetime | None:
        stored = self._settings_repo.get(key)
        if not stored:
            return None
        try:
            return datetime.fromisoformat(stored)
        except ValueError:
            return None

    def _cached_latest(self) -> AppVersion | None:
        stored = self._settings_repo.get(UPDATE_LATEST_VERSION_KEY)
        if not stored:
            return None
        try:
            return AppVersion.parse(stored)
        except ValueError:
            return None

    def _remember(self, fetched: AppVersion | None) -> None:
        """Best-effort: a long operation refuses writes, and the answer is still good."""
        try:
            with self._unit_of_work.write():
                now = self._clock.now()
                if fetched is None:
                    retry_at = now + UPDATE_RETRY_INTERVAL
                    self._settings_repo.set(UPDATE_RETRY_AT_KEY, retry_at.isoformat())
                    return
                self._settings_repo.set(UPDATE_CHECKED_AT_KEY, now.isoformat())
                self._settings_repo.set(UPDATE_LATEST_VERSION_KEY, str(fetched))
        except LongOperationInProgressError:
            return

    def _entries_between(self, current: AppVersion, latest: AppVersion) -> list[ChangelogEntryDTO]:
        text = self._source.changelog_text(latest)
        if text is None:
            return []
        return [
            ChangelogEntryDTO.from_entry(entry)
            for entry in self._parser.parse(text)
            if current < entry.version <= latest
        ]
