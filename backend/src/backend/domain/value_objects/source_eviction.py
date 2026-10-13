from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SourceEviction:
    """Where a source lay before its collection was deleted, and where the deletion put it."""

    source_id: int
    previous_collection_id: int
    moved_to_collection_id: int | None
