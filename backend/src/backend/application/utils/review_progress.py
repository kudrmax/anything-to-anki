from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from backend.domain.value_objects.section_tally import EMPTY_TALLY

if TYPE_CHECKING:
    from collections.abc import Collection

    from backend.application.utils.frequent_word_threshold_resolver import (
        FrequentWordThresholdResolver,
    )
    from backend.domain.ports.card_state_query import CardStateQuery
    from backend.domain.value_objects.decision_progress import DecisionProgress


@dataclass(frozen=True)
class SourceProgress:
    """How far the user got with a source, and how many cards it shows."""

    progress: DecisionProgress
    cards: int


class ReviewProgress:
    """How far the user got with a source, by what they know right now. Everything that
    shows or sums progress — a source, its review screen, a collection — takes it from here.

    Reads the stored projection's counts at the current threshold step."""

    def __init__(
        self,
        card_states: CardStateQuery,
        threshold_resolver: FrequentWordThresholdResolver,
    ) -> None:
        self._card_states = card_states
        self._threshold_resolver = threshold_resolver

    def of_sources(self, source_ids: Collection[int]) -> dict[int, SourceProgress]:
        tallies = self._card_states.section_tallies(source_ids)
        step = self._threshold_resolver.resolve().zipf
        return {
            source_id: SourceProgress(tally.progress(step), tally.cards)
            for source_id in source_ids
            for tally in (tallies.get(source_id, EMPTY_TALLY),)
        }
