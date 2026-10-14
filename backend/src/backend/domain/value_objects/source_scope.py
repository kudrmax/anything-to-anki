from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class ScopeKind(StrEnum):
    ALL = "all"
    UNSORTED = "unsorted"
    COLLECTION = "collection"


@dataclass(frozen=True)
class SourceScope:
    """What is open on the sources screen: everything, sources without a collection, or a
    collection with its subcollections."""

    kind: ScopeKind
    collection_id: int | None = None

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
    def parse(cls, raw: str) -> SourceScope:
        if raw == ScopeKind.ALL:
            return cls.all()
        if raw == ScopeKind.UNSORTED:
            return cls.unsorted()
        if raw.isdigit():
            return cls.collection(int(raw))
        raise ValueError(f"Unknown scope: {raw!r}")
