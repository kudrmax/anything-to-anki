from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import select

from backend.domain.ports.recent_use_repository import RecentUseRepository
from backend.domain.value_objects.source_scope import ScopeKind
from backend.infrastructure.persistence.models import RecentUseModel

if TYPE_CHECKING:
    from collections.abc import Iterable
    from datetime import datetime

    from sqlalchemy.orm import Session

    from backend.domain.value_objects.recent_use import RecentUse
    from backend.domain.value_objects.source_scope import SourceScope


class SqlaRecentUseRepository(RecentUseRepository):
    """SQLAlchemy implementation of RecentUseRepository: one row per source or collection."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def mark(self, scopes: Iterable[SourceScope], at: datetime) -> None:
        for scope in scopes:
            new = _new_row(scope, at)
            if new is None:
                continue
            found = self._session.scalars(select(RecentUseModel).where(
                RecentUseModel.source_id == new.source_id
                if new.source_id is not None
                else RecentUseModel.collection_id == new.collection_id,
            )).one_or_none()
            if found is None:
                self._session.add(new)
            elif found.used_at < at:
                found.used_at = at
        self._session.flush()

    def list_all(self) -> list[RecentUse]:
        return [model.to_value() for model in self._session.scalars(select(RecentUseModel))]


def _new_row(scope: SourceScope, at: datetime) -> RecentUseModel | None:
    """The row of a source or a collection; None for All and Unsorted."""
    if scope.kind is ScopeKind.SOURCE:
        return RecentUseModel(source_id=scope.source_id, used_at=at)
    if scope.kind is ScopeKind.COLLECTION:
        return RecentUseModel(collection_id=scope.collection_id, used_at=at)
    return None
