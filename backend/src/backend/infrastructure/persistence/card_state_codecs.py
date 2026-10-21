"""How a card's values at every threshold step are stored in a TEXT column. SQL never reads
inside them: they are written and read only through these codecs. A book's cards share a few
hundred distinct values, so each is encoded and decoded once."""
from __future__ import annotations

from functools import lru_cache
from types import MappingProxyType
from typing import TYPE_CHECKING

from backend.domain.value_objects.by_step import NewCountsByStep, SectionsByStep
from backend.domain.value_objects.candidate_section import CandidateSection

if TYPE_CHECKING:
    from collections.abc import Mapping

_LETTERS: Mapping[CandidateSection, str] = MappingProxyType({
    CandidateSection.READY: "R",
    CandidateSection.EXTRA: "E",
    CandidateSection.PROBABLY_KNOWN: "P",
    CandidateSection.REVIEWED: "V",
})
_SECTIONS: Mapping[str, CandidateSection] = MappingProxyType(
    {letter: section for section, letter in _LETTERS.items()},
)
COUNT_SEPARATOR = ","
# Far more than a book has: the counts of a phrase's new words stay small.
DISTINCT_VALUES_KEPT = 4096


class SectionsByStepCodec:
    """One letter per threshold step: "RRREEPPV"."""

    @staticmethod
    @lru_cache(maxsize=DISTINCT_VALUES_KEPT)
    def encode(sections: SectionsByStep) -> str:
        return "".join(_LETTERS[section] for section in sections.sections)

    @staticmethod
    @lru_cache(maxsize=DISTINCT_VALUES_KEPT)
    def decode(stored: str) -> SectionsByStep:
        return SectionsByStep(tuple(_SECTIONS[letter] for letter in stored))


class NewCountsByStepCodec:
    """The counts in step order, comma-separated: "0,0,1,1,2,2,3,3"."""

    @staticmethod
    @lru_cache(maxsize=DISTINCT_VALUES_KEPT)
    def encode(counts: NewCountsByStep) -> str:
        return COUNT_SEPARATOR.join(str(count) for count in counts.counts)

    @staticmethod
    @lru_cache(maxsize=DISTINCT_VALUES_KEPT)
    def decode(stored: str) -> NewCountsByStep:
        return NewCountsByStep(tuple(int(count) for count in stored.split(COUNT_SEPARATOR)))
