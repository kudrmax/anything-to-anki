"""The live cards of one source counted by their stored sections at every threshold step."""
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from backend.domain.services.card_view import counted_progress

if TYPE_CHECKING:
    from collections.abc import Mapping

    from backend.domain.value_objects.by_step import SectionsByStep
    from backend.domain.value_objects.decision_progress import DecisionProgress


@dataclass(frozen=True)
class SectionTally:
    """How many live cards of a source stand in each set of sections."""

    counts: Mapping[SectionsByStep, int]

    @property
    def cards(self) -> int:
        return sum(self.counts.values())

    def progress(self, step: float | None) -> DecisionProgress:
        """Reviewed / (Reviewed + Ready) at the threshold step."""
        return counted_progress(
            (sections.at(step), count) for sections, count in self.counts.items()
        )


EMPTY_TALLY = SectionTally({})
