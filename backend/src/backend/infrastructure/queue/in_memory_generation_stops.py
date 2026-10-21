from __future__ import annotations

from threading import Lock
from typing import TYPE_CHECKING

from backend.domain.ports.generation_stops import GenerationStops

if TYPE_CHECKING:
    from collections.abc import Collection

    from backend.domain.value_objects.job_type import JobType


class InMemoryGenerationStops(GenerationStops):
    """The stops in the app's memory: a run lives in the app's process, so a restart ends
    the run and its stops together. Requests run on threads, so a lock guards the list."""

    def __init__(self) -> None:
        self._lock = Lock()
        self._stops: list[tuple[JobType | None, int | None]] = []

    def mark(self) -> int:
        with self._lock:
            return len(self._stops)

    def stop(self, job_type: JobType | None, source_id: int | None) -> None:
        with self._lock:
            self._stops.append((job_type, source_id))

    def stopped_since(
        self, mark: int, job_type: JobType, source_ids: Collection[int],
    ) -> set[int]:
        with self._lock:
            since = self._stops[mark:]
        stopped: set[int] = set()
        for kind, source_id in since:
            if kind is not None and kind is not job_type:
                continue
            if source_id is None:
                return set(source_ids)
            if source_id in source_ids:
                stopped.add(source_id)
        return stopped
