from __future__ import annotations

from abc import ABC, abstractmethod


class SourceOperationLock(ABC):
    """Port for the one long operation a source may be busy with."""

    @abstractmethod
    def acquire(self, source_id: int, kind: str) -> bool:
        """Take the source for an operation; False if another one holds it."""

    @abstractmethod
    def release(self, source_id: int) -> None: ...

    @abstractmethod
    def held(self, source_id: int) -> str | None:
        """The kind of operation holding the source, if any."""

    @abstractmethod
    def clear_all(self) -> None:
        """Release every source: no operation survives a restart of the app."""
