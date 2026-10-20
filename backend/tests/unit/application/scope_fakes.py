from __future__ import annotations

from backend.application.utils.source_scope_resolver import SourceScopeResolver
from backend.domain.entities.source import Source
from backend.domain.value_objects.source_status import SourceStatus

from tests.unit.application.collection_fakes import InMemoryCollectionRepository
from tests.unit.application.source_fakes import InMemorySourceRepository


def empty_scope_resolver() -> SourceScopeResolver:
    """Resolver over no sources and no collections, for tests that never narrow by scope."""
    return SourceScopeResolver(InMemorySourceRepository([]), InMemoryCollectionRepository())


def sources_scope_resolver(*source_ids: int) -> SourceScopeResolver:
    """Resolver over plain sources with these ids: a test exports one of them as its scope."""
    sources = [Source(id=source_id, status=SourceStatus.DONE) for source_id in source_ids]
    return SourceScopeResolver(InMemorySourceRepository(sources), InMemoryCollectionRepository())
