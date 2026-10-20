from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from contextlib import AbstractContextManager


class UnitOfWork(ABC):
    """Port for the transactions of a use case that owns its session."""

    @abstractmethod
    def write(self) -> AbstractContextManager[None]:
        """One write transaction, taken at its start so no other writer can come between
        its reads and its writes; committed on exit, rolled back on an error. What the user
        knows is read again inside it, not taken from before it. Opening it inside another
        write on the same session, through any unit of work, raises NestedWriteError and
        leaves the open one as is."""
