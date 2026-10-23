from __future__ import annotations

from abc import ABC, abstractmethod


class LongOperationLock(ABC):
    """Port for the lock a long operation holds: while it is held, nothing else writes."""

    @abstractmethod
    def take(self) -> None:
        """Raises LongOperationInProgressError if a long operation already holds it."""

    @abstractmethod
    def held(self) -> bool: ...

    @abstractmethod
    def release(self) -> None:
        """Nothing happens if it is not held."""
