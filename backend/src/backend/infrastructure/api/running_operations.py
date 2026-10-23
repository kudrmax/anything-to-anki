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
    """What a long operation must not start beside, in this process: a preview of a set of
    sources and the index build. Both run in the API process, as long operations do."""

    def __init__(self, operations: SourceOperationRegistry, builds: BootstrapBuilds) -> None:
        self._operations = operations
        self._builds = builds

    def any_running(self) -> bool:
        return self._operations.preview_running() or self._builds.running()
