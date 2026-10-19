from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from backend.domain.value_objects.cefr_level import CEFRLevel

if TYPE_CHECKING:
    from backend.domain.entities.occurrence import OccurrenceKey
    from backend.domain.value_objects.cefr_breakdown import CEFRBreakdown, ReducedBreakdown
    from backend.domain.value_objects.document_position import DocumentPosition
    from backend.domain.value_objects.phrase import Phrase
    from backend.domain.value_objects.usage_distribution import UsageDistribution


@dataclass(frozen=True)
class WordKey:
    """What makes a word of a source one word: its lemma without case and the phrasal flag."""

    lemma: str
    is_phrasal_verb: bool

    @staticmethod
    def of(lemma: str, is_phrasal_verb: bool) -> WordKey:
        return WordKey(lemma=lemma.lower(), is_phrasal_verb=is_phrasal_verb)


@dataclass(frozen=True, eq=False)
class WordData:
    """What the analysis knows of a word, apart from its phrases.

    Breakdowns are compared by what the store keeps of them (`CEFRBreakdown.reduced`).
    """

    pos: str
    cefr_level: str | None
    zipf_frequency: float
    usage_distribution: UsageDistribution | None
    occurrence_count: int
    cefr_breakdown: CEFRBreakdown | None = None

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, WordData):
            return NotImplemented
        return (
            self.pos == other.pos
            and _level(self.cefr_level) == _level(other.cefr_level)
            and self.zipf_frequency == other.zipf_frequency
            and self.occurrence_count == other.occurrence_count
            and _groups(self.usage_distribution) == _groups(other.usage_distribution)
            and _reduced(self.cefr_breakdown) == _reduced(other.cefr_breakdown)
        )

    def __hash__(self) -> int:
        return hash(
            (self.pos, _level(self.cefr_level), self.zipf_frequency, self.occurrence_count),
        )


def _reduced(breakdown: CEFRBreakdown | None) -> ReducedBreakdown | None:
    return breakdown.reduced() if breakdown is not None else None


def _level(cefr_level: str | None) -> str | None:
    """An unknown level is no level."""
    return None if cefr_level == CEFRLevel.UNKNOWN.name else cefr_level


def _groups(usage: UsageDistribution | None) -> dict[str, float] | None:
    """No distribution and an empty one are the same: the word is neutral."""
    if usage is None or not usage.groups:
        return None
    return usage.groups


@dataclass(frozen=True)
class BuiltOccurrence:
    """One place of a word in the analysed text and its phrase there; a lower score is a
    better phrase."""

    phrase: Phrase
    phrase_position: DocumentPosition
    key: OccurrenceKey
    fragment_score: float


@dataclass(frozen=True)
class BuiltWord:
    """A word the analysis found worth learning, with every place it occurs, in reading
    order."""

    lemma: str
    is_phrasal_verb: bool
    pos: str
    cefr_level: str | None
    cefr_breakdown: CEFRBreakdown | None
    zipf_frequency: float
    usage_distribution: UsageDistribution | None
    occurrences: tuple[BuiltOccurrence, ...]

    @property
    def key(self) -> WordKey:
        return WordKey.of(self.lemma, self.is_phrasal_verb)

    @property
    def data(self) -> WordData:
        return WordData(
            pos=self.pos,
            cefr_level=self.cefr_level,
            zipf_frequency=self.zipf_frequency,
            usage_distribution=self.usage_distribution,
            occurrence_count=len(self.occurrences),
            cefr_breakdown=self.cefr_breakdown,
        )
