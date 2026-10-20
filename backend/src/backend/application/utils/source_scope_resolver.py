from __future__ import annotations

from typing import TYPE_CHECKING

from backend.domain.exceptions import ScopeNotReviewableError, SourceNotFoundError
from backend.domain.services.collection_tree import CollectionTree
from backend.domain.value_objects.source_scope import ScopeKind

if TYPE_CHECKING:
    from backend.domain.entities.source import Source
    from backend.domain.ports.collection_repository import CollectionRepository
    from backend.domain.ports.source_repository import SourceRepository
    from backend.domain.value_objects.source_scope import SourceScope

ALL_TITLE = "All sources"
UNSORTED_TITLE = "Unsorted"
PATH_SEPARATOR = " / "


class SourceScopeResolver:
    """Which sources a scope holds: a collection brings its subcollections along, a source
    is a set of one."""

    def __init__(
        self,
        source_repo: SourceRepository,
        collection_repo: CollectionRepository,
    ) -> None:
        self._source_repo = source_repo
        self._collection_repo = collection_repo

    def tree(self) -> CollectionTree:
        return CollectionTree(self._collection_repo.list_all())

    def sources(self, scope: SourceScope) -> list[Source]:
        if scope.kind is ScopeKind.SOURCE:
            return [self._source(scope)]
        sources = self._source_repo.list_all()
        if scope.kind is ScopeKind.ALL:
            return sources
        if scope.kind is ScopeKind.UNSORTED:
            return [s for s in sources if s.collection_id is None]
        assert scope.collection_id is not None
        ids = self.tree().subtree_ids(scope.collection_id)
        return [s for s in sources if s.collection_id in ids]

    def reviewable_sources(self, scope: SourceScope) -> list[Source]:
        """The sources of a set opened for review, in the set's order."""
        if not scope.is_reviewable:
            raise ScopeNotReviewableError(scope.kind.value)
        return self.sources(scope)

    def title(self, scope: SourceScope) -> str:
        if scope.kind is ScopeKind.SOURCE:
            return self._source(scope).title or ""
        if scope.kind is ScopeKind.ALL:
            return ALL_TITLE
        if scope.kind is ScopeKind.UNSORTED:
            return UNSORTED_TITLE
        assert scope.collection_id is not None
        return PATH_SEPARATOR.join(self.tree().path(scope.collection_id))

    def _source(self, scope: SourceScope) -> Source:
        assert scope.source_id is not None
        source = self._source_repo.get_by_id(scope.source_id)
        if source is None:
            raise SourceNotFoundError(scope.source_id)
        return source
