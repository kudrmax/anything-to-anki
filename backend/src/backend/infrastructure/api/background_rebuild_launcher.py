from __future__ import annotations

import logging
import threading
from collections.abc import Callable
from typing import TYPE_CHECKING

from backend.domain.ports.sources_rebuild_launcher import SourcesRebuildLauncher
from backend.domain.value_objects.rebuild_mode import RebuildMode
from backend.domain.value_objects.source_scope import SourceScope

if TYPE_CHECKING:
    from sqlalchemy.orm import Session, sessionmaker

    from backend.application.use_cases.scope_operation import ScopeOperationUseCase

logger = logging.getLogger(__name__)

Spawn = Callable[[Callable[[], None]], None]


def spawn_in_thread(work: Callable[[], None]) -> None:
    threading.Thread(target=work, name="rebuild-all-sources", daemon=True).start()


class RebuildPasses:
    """Runs full passes one at a time. A request during a pass does not start a second one
    beside it: it asks for exactly one more pass after the current one, so a pass that
    began before the latest settings were saved is always followed by one that reads them."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._running = False
        self._again = False

    def request(self, spawn: Spawn, run_pass: Callable[[], None]) -> None:
        with self._lock:
            if self._running:
                self._again = True
                return
            self._running = True
        spawn(lambda: self._work(run_pass))

    def _work(self, run_pass: Callable[[], None]) -> None:
        while True:
            try:
                run_pass()
            except Exception:
                logger.exception("rebuild of all sources: the pass failed")
            with self._lock:
                if not self._again:
                    self._running = False
                    return
                self._again = False


REBUILD_PASSES = RebuildPasses()


class BackgroundSourcesRebuildLauncher(SourcesRebuildLauncher):
    """Updates every source on a worker of its own, the way Update of All does: each
    takes its lock only when its turn comes, and a source that is busy then is skipped."""

    def __init__(
        self,
        session_factory: sessionmaker[Session],
        scope_operation: Callable[[Session], ScopeOperationUseCase],
        spawn: Spawn = spawn_in_thread,
        passes: RebuildPasses = REBUILD_PASSES,
    ) -> None:
        self._session_factory = session_factory
        self._scope_operation = scope_operation
        self._spawn = spawn
        self._passes = passes

    def rebuild_all(self) -> None:
        self._passes.request(self._spawn, self._rebuild_pass)

    def _rebuild_pass(self) -> None:
        with self._session_factory() as session:
            summary = self._scope_operation(session).rebuild(
                SourceScope.all(), RebuildMode.UPDATE,
            )
        logger.info(
            "rebuild of all sources: done (skipped=%d, failed=%d)",
            summary.skipped, summary.failed,
        )
