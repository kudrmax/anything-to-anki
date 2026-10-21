"""How a card's values at every threshold step are stored in a TEXT column. SQL never reads
inside them: they are written and read only through these codecs. A book's cards share a few
hundred distinct values, so each is encoded and decoded once."""
from __future__ import annotations

from functools import lru_cache
from types import MappingProxyType
from typing import TYPE_CHECKING

from backend.domain.value_objects.by_step import NewCountsByStep, SectionsByStep
from backend.domain.value_objects.candidate_section import CandidateSection
from backend.domain.value_objects.generated_parts import GeneratedParts
from backend.domain.value_objects.generation_kind import GenerationKind

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

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


# The card_states column telling whether the result of each kind is made, and the one
# telling whether the phrase has its timecodes in the video, which a clip needs.
DONE_COLUMNS: Mapping[GenerationKind, str] = MappingProxyType({
    GenerationKind.POLISH: "polish_done",
    GenerationKind.MEANING: "meaning_done",
    GenerationKind.MEDIA: "media_done",
    GenerationKind.TTS: "tts_done",
    GenerationKind.PRONUNCIATION: "pronunciation_done",
})
TIMED_COLUMN = "media_timed"
GENERATED_COLUMNS: tuple[str, ...] = (*DONE_COLUMNS.values(), TIMED_COLUMN)


class GeneratedPartsCodec:
    """One boolean column per kind, then whether a clip can be cut: in GENERATED_COLUMNS
    order."""

    @staticmethod
    def encode(parts: GeneratedParts) -> tuple[bool, ...]:
        return (
            *(kind in parts.done for kind in DONE_COLUMNS),
            GenerationKind.MEDIA not in parts.uncovered,
        )

    @staticmethod
    def decode(values: Sequence[object]) -> GeneratedParts:
        *done, timed = (bool(value) for value in values)
        return _generated(tuple(done), timed=timed)


@lru_cache(maxsize=DISTINCT_VALUES_KEPT)
def _generated(done: tuple[bool, ...], *, timed: bool) -> GeneratedParts:
    return GeneratedParts(
        done=frozenset(kind for kind, made in zip(DONE_COLUMNS, done, strict=True) if made),
        uncovered=frozenset() if timed else frozenset({GenerationKind.MEDIA}),
    )
