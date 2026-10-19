"""Light phrase rows, words and analysis results for tests of selection and rebuild."""
from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from backend.domain.entities.occurrence import OccurrenceKey
from backend.domain.services.cefr_level_resolver import resolve_cefr_level
from backend.domain.value_objects.built_analysis import BuiltOccurrence, BuiltWord, WordData
from backend.domain.value_objects.card_choice import Binding, CardChoice, NoteKind
from backend.domain.value_objects.cefr_breakdown import (
    CAMBRIDGE,
    CEFRPY,
    EFLLEX,
    KELLY,
    OXFORD,
    CEFRBreakdown,
    SourceVote,
)
from backend.domain.value_objects.cefr_level import CEFRLevel
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
EXPORTED = Binding(NoteKind.LEARN, datetime(2026, 1, 1, tzinfo=UTC))
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
    replaces: bool = False,
    choice: CardChoice | None = None,
) -> OccurrenceRow:
    """A phrase row; its key is at `line` (the id unless given). `is_decision` makes it a
    Learn decision, `choice` any other, `exported` puts it in Anki."""
    at = id if line is None else line
    if choice is None:
        choice = (
            CardChoice.LEARN if is_decision else CardChoice.SKIP if skipped else CardChoice.NONE
        )
    return OccurrenceRow(
        id=id,
        candidate_id=candidate_id,
        key=key_at(at),
        origin=origin,
        shown_by=shown,
        choice=choice,
        revision=revision,
        edited_by_user=edited,
        has_results=has_results,
        binding=EXPORTED if exported else None,
        has_active_job=has_job,
        text_hash=OccurrenceRow.hash_text(text),
        fragment_score=score,
        shows_polish=shows_polish,
        replaces_selection=replaces,
        phrase_hash=OccurrenceRow.hash_phrase(
            text_phrase(text, variant=variant), position_at(at, text),
        ),
    )


def data(*, pos: str = "VERB", zipf: float = 3.0, count: int = 1) -> WordData:
    return WordData(
        pos=pos, cefr_level=None, cefr_breakdown=None, zipf_frequency=zipf,
        usage_distribution=None, occurrence_count=count,
    )


def word(
    id: int = WORD_ID,  # noqa: A002 — named as the field it fills
    lemma: str = "glare",
    *,
    status: WordStatus = WordStatus.NEW,
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
        lemma=lemma, is_phrasal_verb=False, pos=pos, cefr_level=None, cefr_breakdown=None,
        zipf_frequency=zipf, usage_distribution=None, occurrences=tuple(occurrences),
    )


def _vote(name: str, level: CEFRLevel) -> SourceVote:
    return SourceVote(source_name=name, distribution={level: 1.0}, top_level=level)


def breakdown(oxford: CEFRLevel, efllex: dict[CEFRLevel, float]) -> CEFRBreakdown:
    """A breakdown as the analysis makes it: Oxford's level and EFLLex's distribution."""
    priority = [_vote(OXFORD, oxford), _vote(CAMBRIDGE, CEFRLevel.UNKNOWN)]
    votes = [
        _vote(CEFRPY, CEFRLevel.UNKNOWN),
        SourceVote(
            source_name=EFLLEX, distribution=efllex,
            top_level=max(efllex, key=lambda level: efllex[level]),
        ),
        _vote(KELLY, CEFRLevel.UNKNOWN),
    ]
    final, method = resolve_cefr_level(priority, votes)
    return CEFRBreakdown(
        final_level=final, decision_method=method, priority_votes=priority, votes=votes,
    )
