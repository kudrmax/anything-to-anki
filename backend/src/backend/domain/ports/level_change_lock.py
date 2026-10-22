from __future__ import annotations

from abc import ABC, abstractmethod


class LevelChangeLock(ABC):
    """Port for the lock a level change holds: while it is held, nothing else writes."""

    @abstractmethod
    def take(self) -> None:
        """Raises LevelChangeInProgressError if a level change already holds it."""

    @abstractmethod
    def held(self) -> bool: ...

    @abstractmethod
    def release(self) -> None:
        """Nothing happens if it is not held."""
