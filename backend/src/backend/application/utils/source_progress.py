"""How far the user got with each source: what the order of sources reads, from the stored
projection (`ReviewProgress`) or from the facts (`LiveSourceProgress`)."""
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from collections.abc import Collection

    from backend.domain.value_objects.decision_progress import DecisionProgress


@dataclass(frozen=True)
class SourceProgress:
    """How far the user got with a source, and how many cards it shows."""

    progress: DecisionProgress
    cards: int


class SourceProgressReader(Protocol):
    def of_sources(self, source_ids: Collection[int]) -> dict[int, SourceProgress]:
        """Every source given, one without cards included."""
        ...
