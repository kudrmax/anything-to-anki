"""How a card's values at every threshold step are stored in a TEXT column. SQL never reads
inside them: they are written and read only through these codecs."""
from __future__ import annotations

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


class SectionsByStepCodec:
    """One letter per threshold step: "RRREEPPV"."""

    @staticmethod
    def encode(sections: SectionsByStep) -> str:
        return "".join(_LETTERS[section] for section in sections.sections)

    @staticmethod
    def decode(stored: str) -> SectionsByStep:
        return SectionsByStep(tuple(_SECTIONS[letter] for letter in stored))


class NewCountsByStepCodec:
    """The counts in step order, comma-separated: "0,0,1,1,2,2,3,3"."""

    @staticmethod
    def encode(counts: NewCountsByStep) -> str:
        return COUNT_SEPARATOR.join(str(count) for count in counts.counts)

    @staticmethod
    def decode(stored: str) -> NewCountsByStep:
        return NewCountsByStep(tuple(int(count) for count in stored.split(COUNT_SEPARATOR)))
