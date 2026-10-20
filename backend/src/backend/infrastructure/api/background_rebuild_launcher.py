from __future__ import annotations

import logging
import threading
from collections.abc import Callable
from typing import TYPE_CHECKING

from backend.domain.exceptions import DomainError, SourceOperationBusyError
from backend.domain.ports.sources_rebuild_launcher import SourcesRebuildLauncher
from backend.domain.services.source_operations import available_operations
from backend.domain.value_objects.source_operation_kind import SourceOperationKind
from backend.infrastructure.persistence.sqla_source_repository import SqlaSourceRepository

if TYPE_CHECKING:
    from sqlalchemy.orm import Session, sessionmaker

    from backend.application.use_cases.rebuild_source import RebuildSourceUseCase
    from backend.infrastructure.api.source_operations import SourceOperationRegistry

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
    """Rebuilds the sources one after another on a worker of its own, the way the Rebuild
    button does: each takes its lock only when its turn comes, and a source that is busy
    then is skipped."""

    def __init__(
        self,
        session_factory: sessionmaker[Session],
        rebuild_use_case: Callable[[Session], RebuildSourceUseCase],
        operations: SourceOperationRegistry,
        spawn: Spawn = spawn_in_thread,
        passes: RebuildPasses = REBUILD_PASSES,
    ) -> None:
        self._session_factory = session_factory
        self._rebuild_use_case = rebuild_use_case
        self._operations = operations
        self._spawn = spawn
        self._passes = passes

    def rebuild_all(self) -> None:
        self._passes.request(self._spawn, self._rebuild_each)

    def _rebuild_each(self) -> None:
        try:
            source_ids = self._rebuildable_source_ids()
        except Exception:
            logger.exception("rebuild of all sources: listing the sources failed")
            return
        for source_id in source_ids:
            self._rebuild(source_id)

    def _rebuildable_source_ids(self) -> list[int]:
        with self._session_factory() as session:
            return [
                source.id
                for source in SqlaSourceRepository(session).list_all()
                if source.id is not None
                and SourceOperationKind.REBUILD in available_operations(source)
            ]

    def _rebuild(self, source_id: int) -> None:
        with self._session_factory() as session:
            use_case = self._rebuild_use_case(session)
            try:
                use_case.start(source_id, SourceOperationKind.REBUILD)
            except SourceOperationBusyError:
                logger.info("rebuild of all sources: source %d is busy, skipped", source_id)
                return
            except DomainError:
                logger.exception("rebuild of all sources: source %d can't start", source_id)
                return
            session.commit()
            operation = self._operations.started(source_id, SourceOperationKind.REBUILD)
            try:
                summary = use_case.run(source_id, include_open=False)
            except Exception as e:
                logger.exception("rebuild of all sources: source %d failed", source_id)
                self._operations.failed(source_id, operation.operation_id, str(e))
            else:
                self._operations.finished(source_id, operation.operation_id, summary=summary)
