from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from backend.domain.value_objects.held_operation import HeldOperation
    from backend.domain.value_objects.processing_stage import ProcessingStage
    from backend.domain.value_objects.source_operation_kind import SourceOperationKind


class SourceOperationLock(ABC):
    """Port for the one long operation a source may be busy with."""

    @abstractmethod
    def acquire(self, source_id: int, kind: SourceOperationKind) -> bool:
        """Take the source for an operation; False if another one holds it."""

    @abstractmethod
    def release(self, source_id: int) -> None: ...

    @abstractmethod
    def held(self, source_id: int) -> SourceOperationKind | None:
        """The kind of operation holding the source, if any."""

    @abstractmethod
    def set_stage(self, source_id: int, stage: ProcessingStage) -> None:
        """What the operation holding the source is doing now."""

    @abstractmethod
    def operations(self) -> dict[int, HeldOperation]:
        """Every busy source with its operation."""

    @abstractmethod
    def clear_all(self) -> None:
        """Release every source: no operation survives a restart of the app."""
