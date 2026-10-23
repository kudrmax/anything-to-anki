from __future__ import annotations

import logging
import threading
from typing import TYPE_CHECKING

from backend.application.utils.level_change_launcher import LevelChangeLauncher
from backend.domain.exceptions import LongOperationInProgressError
from backend.domain.value_objects.long_operation_kind import LongOperationKind

if TYPE_CHECKING:
    from collections.abc import Callable

    from backend.application.dto.settings_dtos import UpdateSettingsRequest
    from backend.application.use_cases.start_level_change import StartLevelChangeUseCase
    from backend.application.utils.long_operation_progress import LongOperationProgress

logger = logging.getLogger(__name__)

type LevelChangeRun = Callable[[UpdateSettingsRequest], None]


def in_thread(run: Callable[[], None]) -> None:
    threading.Thread(target=run, name="level-change", daemon=True).start()


class BackgroundLevelChangeLauncher(LevelChangeLauncher):
    """Starts the change in the request, so a refusal reaches the user, then runs it on a
    thread of its own."""

    def __init__(
        self,
        start: StartLevelChangeUseCase,
        run: LevelChangeRun,
        release: Callable[[], None],
        progress: LongOperationProgress,
        spawn: Callable[[Callable[[], None]], None] = in_thread,
    ) -> None:
        self._start = start
        self._run = run
        self._release = release
        self._progress = progress
        self._spawn = spawn

    def start(self, request: UpdateSettingsRequest) -> None:
        if not self._progress.try_start(LongOperationKind.LEVEL_CHANGE):
            raise LongOperationInProgressError
        try:
            self._start.execute()
        except BaseException:
            self._progress.abandon()
            raise
        self._spawn(lambda: self._run_logged(request))

    def _run_logged(self, request: UpdateSettingsRequest) -> None:
        """The change ends itself in every case; this only keeps a crash before it began
        from leaving the lock held and the progress running."""
        try:
            self._run(request)
        except Exception as e:
            logger.exception("level change: could not run")
            try:
                self._release()
            except Exception:
                logger.exception("level change: its lock could not be dropped")
            self._progress.fail(str(e))
