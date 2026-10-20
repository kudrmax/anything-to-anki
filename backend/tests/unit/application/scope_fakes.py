from __future__ import annotations

from datetime import UTC, datetime

from backend.application.utils.source_scope_resolver import SourceScopeResolver
from backend.domain.entities.source import Source
from backend.domain.value_objects.source_status import SourceStatus

from tests.unit.application.collection_fakes import InMemoryCollectionRepository
from tests.unit.application.source_fakes import InMemorySourceRepository

# One moment for every source: the set keeps the order the sources were given in.
_CREATED = datetime(2026, 1, 1, tzinfo=UTC)


def empty_scope_resolver() -> SourceScopeResolver:
    """Resolver over no sources and no collections, for tests that never narrow by scope."""
    return SourceScopeResolver(InMemorySourceRepository([]), InMemoryCollectionRepository())


def sources_scope_resolver(*source_ids: int) -> SourceScopeResolver:
    """Resolver over plain sources with these ids, the whole set in the order given: a test
    exports one of them or all as its scope."""
    sources = [
        Source(id=source_id, status=SourceStatus.DONE, created_at=_CREATED)
        for source_id in source_ids
    ]
    return SourceScopeResolver(InMemorySourceRepository(sources), InMemoryCollectionRepository())
