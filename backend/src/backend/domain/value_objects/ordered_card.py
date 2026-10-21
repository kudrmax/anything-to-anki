from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from backend.domain.value_objects.frequency_band import FrequencyBand

if TYPE_CHECKING:
    from backend.domain.value_objects.by_step import NewCountsByStep, SectionsByStep
    from backend.domain.value_objects.usage_distribution import UsageDistribution


@dataclass(frozen=True, slots=True)
class OrderedCard:
    """A card as the review order needs it, light: what the sort keys read of its word and
    phrase, and its stored standing at every threshold step. A book opens with a hundred
    thousand of them.

    `place`: (block, start_line, start_char) of the phrase in its document; None for a
    phrase without a place."""

    phrase_id: int
    word_id: int
    source_id: int
    lemma: str
    pos: str
    zipf_frequency: float
    cefr_level: str | None
    occurrences: int
    is_phrasal_verb: bool
    usage_distribution: UsageDistribution | None
    place: tuple[int, int, int] | None
    is_done: bool
    sections: SectionsByStep
    new_counts: NewCountsByStep

    @property
    def frequency_band(self) -> FrequencyBand:
        return FrequencyBand.from_zipf(self.zipf_frequency)
