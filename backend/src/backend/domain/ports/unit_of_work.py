from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from contextlib import AbstractContextManager


class UnitOfWork(ABC):
    """Port for the transactions of a use case that owns its session."""

    @abstractmethod
    def commit(self) -> None:
        """Make the work done so far visible to everyone else."""

    @abstractmethod
    def rollback(self) -> None:
        """Drop the work not committed yet."""

    @abstractmethod
    def write(self) -> AbstractContextManager[None]:
        """One write transaction, taken at its start so no other writer can come between
        its reads and its writes; committed on exit, rolled back on an error."""
