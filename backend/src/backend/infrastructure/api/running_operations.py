from __future__ import annotations

import threading
from typing import TYPE_CHECKING

from backend.domain.ports.running_operations import RunningOperations

if TYPE_CHECKING:
    from asyncio import Future

    from backend.infrastructure.api.source_operations import SourceOperationRegistry


class BootstrapBuilds:
    """The index build this process runs, if any; kept in memory, as no build survives a
    restart."""

    def __init__(self) -> None:
        self._guard = threading.Lock()
        self._running: Future[None] | None = None

    def track(self, build: Future[None]) -> None:
        with self._guard:
            self._running = build

    def running(self) -> bool:
        with self._guard:
            return self._running is not None and not self._running.done()


BOOTSTRAP_BUILDS = BootstrapBuilds()


class InProcessRunningOperations(RunningOperations):
    """The long operations of this process: operations over sets of sources and the index
    build. They all run in the API process, as the level change does."""

    def __init__(self, operations: SourceOperationRegistry, builds: BootstrapBuilds) -> None:
        self._operations = operations
        self._builds = builds

    def any_running(self) -> bool:
        return self._operations.any_running() or self._builds.running()
