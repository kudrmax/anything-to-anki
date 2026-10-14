"""Light phrase rows, words and analysis results for tests of selection and rebuild."""
from __future__ import annotations

from typing import TYPE_CHECKING

from backend.domain.entities.occurrence import OccurrenceKey
from backend.domain.value_objects.built_analysis import BuiltOccurrence, BuiltWord, WordData
from backend.domain.value_objects.document_position import DocumentPosition
from backend.domain.value_objects.occurrence_row import OccurrenceRow
from backend.domain.value_objects.phrase_origin_kind import OccurrenceOrigin, ShownBy
from backend.domain.value_objects.word_row import WordRow
from backend.domain.value_objects.word_status import WordStatus

from tests.phrase_support import phrase

if TYPE_CHECKING:
    from backend.domain.value_objects.phrase import Phrase

SELECTION = ShownBy.SELECTION
USER = ShownBy.USER
AUTO = OccurrenceOrigin.AUTO
MANUAL = OccurrenceOrigin.MANUAL
EXAMPLE = OccurrenceOrigin.EXAMPLE
COLLECTED = OccurrenceOrigin.COLLECTED
DEFAULT_TEXT = "He glared at me."
WORD_ID = 1


def key_at(line: int) -> OccurrenceKey:
    return OccurrenceKey(block=0, line=line, char=0)


def position_at(line: int, text: str) -> DocumentPosition:
    return DocumentPosition(
        block=0, start_line=line, start_char=0, end_line=line, end_char=len(text),
    )


def text_phrase(text: str, *, variant: bool = False) -> Phrase:
    """The same text with other facts about its words when `variant`."""
    return phrase(text, new=[text.split()[0]] if variant else [])


def row(
    *,
    id: int,  # noqa: A002 — named as the field it fills
    candidate_id: int = WORD_ID,
    line: int | None = None,
    score: float | None = None,
    shown: ShownBy | None = None,
    origin: OccurrenceOrigin = AUTO,
    skipped: bool = False,
    is_decision: bool = False,
    revision: int = 0,
    edited: bool = False,
    has_results: bool = False,
    exported: bool = False,
    has_job: bool = False,
    text: str = DEFAULT_TEXT,
    variant: bool = False,
    shows_polish: bool = False,
) -> OccurrenceRow:
    """A phrase row; its key is at `line` (the id unless given)."""
    at = id if line is None else line
    return OccurrenceRow(
        id=id,
        candidate_id=candidate_id,
        key=key_at(at),
        origin=origin,
        shown_by=shown,
        skipped=skipped,
        is_decision=is_decision,
        revision=revision,
        edited_by_user=edited,
        has_results=has_results,
        exported=exported,
        has_active_job=has_job,
        text_hash=OccurrenceRow.hash_text(text),
        fragment_score=score,
        shows_polish=shows_polish,
        phrase_hash=OccurrenceRow.hash_phrase(
            text_phrase(text, variant=variant), position_at(at, text),
        ),
    )


def data(*, pos: str = "VERB", zipf: float = 3.0, count: int = 1) -> WordData:
    return WordData(
        pos=pos, cefr_level="B2", cefr_breakdown=None, zipf_frequency=zipf,
        usage_distribution=None, occurrence_count=count,
    )


def word(
    id: int = WORD_ID,  # noqa: A002 — named as the field it fills
    lemma: str = "glare",
    *,
    status: WordStatus = WordStatus.PENDING,
    pos: str = "VERB",
    zipf: float = 3.0,
    count: int = 1,
) -> WordRow:
    return WordRow(
        id=id, lemma=lemma, is_phrasal_verb=False, status=status,
        data=data(pos=pos, zipf=zipf, count=count),
    )


def occ(
    line: int, score: float = 0.5, *, text: str = DEFAULT_TEXT, variant: bool = False,
) -> BuiltOccurrence:
    return BuiltOccurrence(
        phrase=text_phrase(text, variant=variant),
        phrase_position=position_at(line, text),
        key=key_at(line),
        fragment_score=score,
    )


def built(
    lemma: str = "glare",
    *occurrences: BuiltOccurrence,
    pos: str = "VERB",
    zipf: float = 3.0,
) -> BuiltWord:
    return BuiltWord(
        lemma=lemma, is_phrasal_verb=False, pos=pos, cefr_level="B2", cefr_breakdown=None,
        zipf_frequency=zipf, usage_distribution=None, occurrences=tuple(occurrences),
    )
