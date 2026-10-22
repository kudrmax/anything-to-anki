from __future__ import annotations

from abc import ABC, abstractmethod


class RunningOperations(ABC):
    """Port for the long operations a level change must not start beside: those that take
    their sources one by one (Update, Re-cut, Refresh of a set) or hold the database for
    their whole run (the index build). A level change started between two of their steps
    would cut them off half way."""

    @abstractmethod
    def any_running(self) -> bool: ...
