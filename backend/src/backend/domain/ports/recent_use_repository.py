from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterable
    from datetime import datetime

    from backend.domain.value_objects.recent_use import RecentUse
    from backend.domain.value_objects.source_scope import SourceScope


class RecentUseRepository(ABC):
    """Port for the last use of each source and collection."""

    @abstractmethod
    def mark(self, scopes: Iterable[SourceScope], at: datetime) -> None:
        """Each source or collection scope is used at `at`; All and Unsorted are ignored."""

    @abstractmethod
    def list_all(self) -> list[RecentUse]:
        """Every recorded use, in no particular order."""
