from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Collection

    from backend.domain.value_objects.job_type import JobType


class GenerationStops(ABC):
    """The user's stops of generation, in the order made, so a run that queues in parts
    learns of a stop made after it began: it queues nothing more for what was stopped. A
    stop names a kind of job and a source; None for either stops every one."""

    @abstractmethod
    def mark(self) -> int:
        """Where the stops stand now: a run takes it before it chooses its cards."""

    @abstractmethod
    def stop(self, job_type: JobType | None, source_id: int | None) -> None:
        """The user stopped this kind of job for this source."""

    @abstractmethod
    def stopped_since(
        self, mark: int, job_type: JobType, source_ids: Collection[int],
    ) -> set[int]:
        """The sources of these that a stop made after `mark` stopped the kind for."""
