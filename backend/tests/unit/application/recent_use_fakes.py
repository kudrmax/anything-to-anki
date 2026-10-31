from __future__ import annotations

from typing import TYPE_CHECKING

from backend.domain.ports.recent_use_repository import RecentUseRepository
from backend.domain.value_objects.recent_use import USED_KINDS, RecentUse

if TYPE_CHECKING:
    from collections.abc import Iterable
    from datetime import datetime

    from backend.domain.value_objects.source_scope import SourceScope


class InMemoryRecentUseRepository(RecentUseRepository):
    """Port fake: the last use of each item, by scope."""

    def __init__(self) -> None:
        self.uses: dict[SourceScope, datetime] = {}

    def mark(self, scopes: Iterable[SourceScope], at: datetime) -> None:
        for scope in scopes:
            if scope.kind in USED_KINDS and self.uses.get(scope, at) <= at:
                self.uses[scope] = at

    def list_all(self) -> list[RecentUse]:
        return [RecentUse(scope=scope, used_at=at) for scope, at in self.uses.items()]
