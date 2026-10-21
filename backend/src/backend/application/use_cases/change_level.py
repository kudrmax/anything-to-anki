from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from backend.application.constants import FREQUENT_WORD_THRESHOLD_SETTING
from backend.application.utils.settings_writer import CEFR_LEVEL_SETTING
from backend.application.utils.source_rebuilder import AnalysisValues
from backend.domain.exceptions import LevelChangeCancelledError
from backend.domain.services.level_change_progress import LevelChangeStage
from backend.domain.services.source_operations import REBUILD_OPERATION, available_operations
from backend.domain.value_objects.rebuild_mode import RebuildMode
from backend.domain.value_objects.source_scope import SourceScope

if TYPE_CHECKING:
    from backend.application.dto.settings_dtos import UpdateSettingsRequest
    from backend.application.utils.frequent_word_threshold_resolver import (
        FrequentWordThresholdResolver,
    )
    from backend.application.utils.level_change_progress import LevelChangeProgress
    from backend.application.utils.settings_writer import SettingsWriter
    from backend.application.utils.source_rebuilder import AnalysedSource, SourceRebuilder
    from backend.application.utils.source_scope_resolver import SourceScopeResolver
    from backend.domain.ports.level_change_lock import LevelChangeLock
    from backend.domain.ports.media_files import MediaFiles
    from backend.domain.ports.unit_of_work import UnitOfWork

logger = logging.getLogger(__name__)

MODE = RebuildMode.UPDATE


class ChangeLevelUseCase:
    """Saves settings that change the analysis together with «Find words again» of every
    source and the card states, in one write: all of it or none.

    Runs once StartLevelChangeUseCase holds the lock, on a unit of work that owns it: every
    source is analysed with the new values first, outside any transaction — nothing else
    writes meanwhile — then everything is applied in one write that drops the lock too.
    Cancelled or failed, nothing is written and the lock is dropped. Files of what the
    change dropped go once it is committed."""

    def __init__(
        self,
        settings_writer: SettingsWriter,
        threshold_resolver: FrequentWordThresholdResolver,
        scope_resolver: SourceScopeResolver,
        rebuilder: SourceRebuilder,
        lock: LevelChangeLock,
        media_files: MediaFiles,
        unit_of_work: UnitOfWork,
        progress: LevelChangeProgress,
    ) -> None:
        self._settings_writer = settings_writer
        self._threshold_resolver = threshold_resolver
        self._scope_resolver = scope_resolver
        self._rebuilder = rebuilder
        self._lock = lock
        self._media_files = media_files
        self._unit_of_work = unit_of_work
        self._progress = progress

    def execute(self, request: UpdateSettingsRequest) -> None:
        try:
            analysed = self._analyse_all(self._values(request))
            dropped_files = self._apply_all(request, analysed)
        except LevelChangeCancelledError:
            logger.info("level change: cancelled, nothing changed")
            self._release()
            self._progress.cancelled()
            return
        except Exception as e:
            logger.exception("level change: failed, nothing changed")
            self._release()
            self._progress.fail(str(e))
            return
        self._media_files.remove(dropped_files)
        self._progress.succeed()
        logger.info("level change: done (sources=%d)", len(analysed))

    def _values(self, request: UpdateSettingsRequest) -> AnalysisValues:
        threshold = self._settings_writer.after(request, FREQUENT_WORD_THRESHOLD_SETTING)
        return AnalysisValues(
            user_level=self._settings_writer.after(request, CEFR_LEVEL_SETTING),
            frequent_word_zipf=self._threshold_resolver.resolve_for(threshold).zipf,
        )

    def _targets(self) -> list[int]:
        offered = REBUILD_OPERATION[MODE]
        return [
            source.id for source in self._scope_resolver.sources(SourceScope.all())
            if source.id is not None and offered in available_operations(source)
        ]

    def _analyse_all(self, values: AnalysisValues) -> list[AnalysedSource]:
        targets = self._targets()
        analysed: list[AnalysedSource] = []
        for done, source_id in enumerate(targets):
            self._progress.check_cancel()
            self._progress.step(LevelChangeStage.ANALYSE, done, len(targets))
            analysed.append(self._rebuilder.analyse(source_id, values))
        return analysed

    def _apply_all(
        self, request: UpdateSettingsRequest, analysed: list[AnalysedSource],
    ) -> list[str]:
        dropped_files: list[str] = []
        with self._unit_of_work.write():
            self._settings_writer.write(request)
            for done, source in enumerate(analysed):
                self._progress.check_cancel()
                self._progress.step(LevelChangeStage.APPLY, done, len(analysed))
                dropped_files += self._rebuilder.apply_inside(source, MODE).dropped_files
            self._progress.enter_finish()
            self._lock.release()
        return dropped_files

    def _release(self) -> None:
        """A lock left behind would keep every write out until the app restarts."""
        try:
            with self._unit_of_work.write():
                self._lock.release()
        except Exception:
            logger.exception("level change: its lock could not be dropped; a restart drops it")
