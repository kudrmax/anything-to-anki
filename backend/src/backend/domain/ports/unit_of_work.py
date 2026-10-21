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

    @abstractmethod
    def read(self) -> AbstractContextManager[None]:
        """One read transaction: every read inside it sees the database as it was at its
        first read, whatever is written meanwhile. Nothing is written inside it: a write,
        flushed or not, and a write() opened in it raise WriteInReadError. Inside an open
        transaction of the session it reads in that one."""
