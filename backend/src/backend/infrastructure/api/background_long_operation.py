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
    from backend.application.use_cases.start_long_operation import StartLongOperationUseCase
    from backend.application.utils.long_operation_progress import LongOperationProgress

logger = logging.getLogger(__name__)

type LevelChangeRun = Callable[[UpdateSettingsRequest], None]


def in_thread(run: Callable[[], None]) -> None:
    threading.Thread(target=run, name="long-operation", daemon=True).start()


class BackgroundLongOperationLauncher:
    """Starts a long operation in the request, so a refusal reaches the user, then runs it
    on a thread of its own."""

    def __init__(
        self,
        start: StartLongOperationUseCase,
        release: Callable[[], None],
        progress: LongOperationProgress,
        spawn: Callable[[Callable[[], None]], None] = in_thread,
    ) -> None:
        self._start = start
        self._release = release
        self._progress = progress
        self._spawn = spawn

    def start(self, kind: LongOperationKind, run: Callable[[], None]) -> None:
        """Takes the lock, or raises why the operation cannot start; then returns at once
        while `run` goes on. `run` ends the operation itself in every case."""
        if not self._progress.try_start(kind):
            raise LongOperationInProgressError
        try:
            self._start.execute()
        except BaseException:
            self._progress.abandon()
            raise
        self._spawn(lambda: self._run_logged(kind, run))

    def _run_logged(self, kind: LongOperationKind, run: Callable[[], None]) -> None:
        """This only keeps a crash before the operation began from leaving the lock held and
        the progress running."""
        try:
            run()
        except Exception as e:
            logger.exception("long operation %s: could not run", kind.value)
            try:
                self._release()
            except Exception:
                logger.exception("long operation %s: its lock could not be dropped", kind.value)
            self._progress.fail(str(e))


class BackgroundLevelChangeLauncher(LevelChangeLauncher):
    """The level change as a long operation in the background."""

    def __init__(self, launcher: BackgroundLongOperationLauncher, run: LevelChangeRun) -> None:
        self._launcher = launcher
        self._run = run

    def start(self, request: UpdateSettingsRequest) -> None:
        self._launcher.start(LongOperationKind.LEVEL_CHANGE, lambda: self._run(request))
