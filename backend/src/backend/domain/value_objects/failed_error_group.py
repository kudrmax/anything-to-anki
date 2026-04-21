from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SourceErrorCount:
    """Per-source count within a failed error group."""

    source_id: int
    source_title: str
    count: int


@dataclass(frozen=True)
class FailedErrorGroup:
    """A group of failed enrichments sharing the same error text."""

    error_text: str
    count: int
    source_counts: list[SourceErrorCount]
    candidate_ids: list[int]
