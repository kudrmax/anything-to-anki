"""How a card's values are stored: its values at every threshold step in a TEXT column, what
was made for it in a column per kind, and a whole stored row as the driver reads it. SQL
never reads inside them: they are written and read only through these codecs. A book's
cards share a few hundred distinct values, so each is encoded and decoded once."""
from __future__ import annotations

from datetime import UTC, datetime
from functools import lru_cache
from types import MappingProxyType
from typing import TYPE_CHECKING, Any

from backend.domain.value_objects.by_step import NewCountsByStep, SectionsByStep
from backend.domain.value_objects.candidate_section import CandidateSection
from backend.domain.value_objects.card_state_rows import CardStateRow, StoredCardState
from backend.domain.value_objects.generated_parts import GeneratedParts, JobState
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
# The kinds made once per word: their job is the word's; every other kind's is the phrase's.
WORD_KINDS: tuple[GenerationKind, ...] = (GenerationKind.PRONUNCIATION,)
# The card_states column telling, for each kind, what the queue holds for the card: a
# JobState.
JOB_COLUMNS: Mapping[GenerationKind, str] = MappingProxyType({
    kind: f"{kind.value}_job" for kind in DONE_COLUMNS
})
GENERATED_COLUMNS: tuple[str, ...] = (
    *DONE_COLUMNS.values(), TIMED_COLUMN, *JOB_COLUMNS.values(),
)


class GeneratedPartsCodec:
    """One boolean column per kind, then whether a clip can be cut, then the job state of
    each kind: in GENERATED_COLUMNS order."""

    @staticmethod
    def encode(parts: GeneratedParts) -> tuple[bool | int, ...]:
        return (
            *(kind in parts.done for kind in DONE_COLUMNS),
            GenerationKind.MEDIA not in parts.uncovered,
            *(int(parts.job_of(kind)) for kind in JOB_COLUMNS),
        )

    # Any: the driver's values are untyped; every one is read into a bool or a job state.
    @staticmethod
    def decode(values: Sequence[Any]) -> GeneratedParts:
        kinds = len(DONE_COLUMNS)
        return _generated(
            tuple(bool(value) for value in values[:kinds]),
            tuple(JobState(int(value)) for value in values[kinds + 1:]),
            timed=bool(values[kinds]),
        )


@lru_cache(maxsize=DISTINCT_VALUES_KEPT)
def _generated(
    done: tuple[bool, ...], jobs: tuple[JobState, ...], *, timed: bool,
) -> GeneratedParts:
    states = dict(zip(JOB_COLUMNS, jobs, strict=True))
    return GeneratedParts(
        done=frozenset(kind for kind, made in zip(DONE_COLUMNS, done, strict=True) if made),
        uncovered=frozenset() if timed else frozenset({GenerationKind.MEDIA}),
        active_jobs=frozenset(k for k, state in states.items() if state is JobState.ACTIVE),
        failed_jobs=frozenset(k for k, state in states.items() if state is JobState.FAILED),
    )


# The columns of a stored card row, as the driver reads and writes them.
CARD_COLUMNS = (
    "phrase_id", "source_id", "word_id", "lemma", "is_done", "wants_generation", "sections",
    "open_sections", "new_counts", *GENERATED_COLUMNS, "changes_at", "revision", "removed",
)
CARD_NAMES = ", ".join(CARD_COLUMNS)
_GENERATED_AT = CARD_COLUMNS.index(GENERATED_COLUMNS[0])
_GENERATED_END = _GENERATED_AT + len(GENERATED_COLUMNS)


# Any: the driver's rows are untyped; each value is read into its typed field here.
def plain_stored_card(values: tuple[Any, ...]) -> StoredCardState:
    """A row of CARD_COLUMNS as the driver gives it: `changes_at` as the UTC text the
    column type stores."""
    (
        phrase_id, source_id, word_id, lemma, is_done, wants_generation, sections, open_sections,
        new_counts,
    ) = values[:_GENERATED_AT]
    generated = values[_GENERATED_AT:_GENERATED_END]
    changes_at, revision, removed = values[_GENERATED_END:]
    return StoredCardState(
        row=CardStateRow(
            phrase_id=phrase_id,
            source_id=source_id,
            word_id=word_id,
            lemma=lemma,
            is_done=bool(is_done),
            wants_generation=bool(wants_generation),
            sections=SectionsByStepCodec.decode(sections),
            open_sections=SectionsByStepCodec.decode(open_sections),
            new_counts=NewCountsByStepCodec.decode(new_counts),
            generated=GeneratedPartsCodec.decode(generated),
            changes_at=(
                datetime.fromisoformat(changes_at).replace(tzinfo=UTC)
                if changes_at is not None else None
            ),
        ),
        revision=revision,
        removed=bool(removed),
    )
