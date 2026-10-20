from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum

SOURCE_PREFIX = "source-"
_SOURCE_TOKEN = re.compile(rf"^{SOURCE_PREFIX}(\d+)$")


class ScopeKind(StrEnum):
    ALL = "all"
    UNSORTED = "unsorted"
    COLLECTION = "collection"
    SOURCE = "source"


@dataclass(frozen=True)
class SourceScope:
    """A set of sources: everything, sources without a collection, a collection with its
    subcollections, or one source."""

    kind: ScopeKind
    collection_id: int | None = None
    source_id: int | None = None

    @classmethod
    def all(cls) -> SourceScope:
        return cls(ScopeKind.ALL)

    @classmethod
    def unsorted(cls) -> SourceScope:
        return cls(ScopeKind.UNSORTED)

    @classmethod
    def collection(cls, collection_id: int) -> SourceScope:
        return cls(ScopeKind.COLLECTION, collection_id)

    @classmethod
    def source(cls, source_id: int) -> SourceScope:
        return cls(ScopeKind.SOURCE, source_id=source_id)

    @property
    def is_reviewable(self) -> bool:
        """Unsorted is a holding folder, not a set to review."""
        return self.kind is not ScopeKind.UNSORTED

    @classmethod
    def parse(cls, raw: str) -> SourceScope:
        if raw == ScopeKind.ALL:
            return cls.all()
        if raw == ScopeKind.UNSORTED:
            return cls.unsorted()
        source_token = _SOURCE_TOKEN.match(raw)
        if source_token is not None:
            return cls.source(int(source_token.group(1)))
        if raw.isdigit():
            return cls.collection(int(raw))
        raise ValueError(f"Unknown scope: {raw!r}")
