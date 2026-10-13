from __future__ import annotations

from backend.application.utils.source_scope_resolver import SourceScopeResolver

from tests.unit.application.collection_fakes import InMemoryCollectionRepository
from tests.unit.application.source_fakes import InMemorySourceRepository


def empty_scope_resolver() -> SourceScopeResolver:
    """Resolver over no sources and no collections, for tests that never narrow by scope."""
    return SourceScopeResolver(InMemorySourceRepository([]), InMemoryCollectionRepository())
