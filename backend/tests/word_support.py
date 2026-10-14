"""Words and their phrases straight in the database, for tests below the repositories."""
from __future__ import annotations

from dataclasses import dataclass, replace
from typing import TYPE_CHECKING

from backend.domain.entities.stored_candidate import StoredCandidate
from backend.domain.value_objects.candidate_status import CandidateStatus
from backend.infrastructure.persistence.models import dump_phrase
from sqlalchemy import text

from tests.phrase_support import phrase

if TYPE_CHECKING:
    from backend.domain.value_objects.document_position import DocumentPosition
    from backend.domain.value_objects.phrase import Phrase
    from backend.domain.value_objects.phrase_origin_kind import OccurrenceOrigin
    from sqlalchemy.engine import Connection
    from sqlalchemy.orm import Session

CREATED_AT = "2026-01-01 00:00:00"


def insert_word(
    db: Session | Connection,
    word_id: int,
    *,
    source_id: int = 1,
    lemma: str | None = None,
    status: str = CandidateStatus.PENDING.value,
    phrase_text: str | None = None,
    pos: str = "NOUN",
    zipf_frequency: float = 3.0,
    is_sweet_spot: bool = False,
) -> None:
    """A word with one shown phrase whose id is the word's id.

    The lemma is `word<id>` unless given: lemmas of a source are unique. `status` may be
    "skip": the word is pending and its phrase is skipped.
    """
    lemma = lemma or f"word{word_id}"
    skipped = status == CandidateStatus.SKIP.value
    db.execute(
        text(
            "INSERT INTO candidates (id, source_id, lemma, pos, zipf_frequency, is_sweet_spot,"
            " occurrences, status, is_phrasal_verb)"
            " VALUES (:id, :source_id, :lemma, :pos, :zipf, :sweet, 1, :status, 0)"
        ),
        {
            "id": word_id, "source_id": source_id, "lemma": lemma, "pos": pos,
            "zipf": zipf_frequency, "sweet": is_sweet_spot,
            "status": CandidateStatus.PENDING.value if skipped else status,
        },
    )
    is_decision = status in (CandidateStatus.LEARN.value, CandidateStatus.KNOWN.value)
    db.execute(
        text(
            "INSERT INTO phrases (id, candidate_id, source_phrase, origin, shown_by, skipped,"
            " is_decision, decision_kind, created_at)"
            " VALUES (:id, :id, :phrase, 'auto', 'selection', :skipped, :decision, :kind,"
            " :created_at)"
        ),
        {
            "id": word_id,
            "phrase": dump_phrase(phrase(phrase_text or lemma, lemma)),
            "skipped": skipped,
            "decision": is_decision,
            "kind": "learn" if is_decision else None,
            "created_at": CREATED_AT,
        },
    )


def store_card(
    session: Session,
    word: StoredCandidate,
    text: Phrase,
    *,
    position: DocumentPosition | None = None,
    origin: OccurrenceOrigin | None = None,
    skipped: bool = False,
) -> tuple[int, int]:
    """A phrase of the word through the repositories; the word is made when the source has
    none of its lemma. A decided word made here decides on this phrase.

    `origin` is `auto` for a new word's phrase with a place in the document, `example`
    without one, `manual` for another phrase of a word. Returns (word id, phrase id).
    """
    from backend.domain.entities.occurrence import Occurrence
    from backend.domain.value_objects.built_analysis import WordKey
    from backend.domain.value_objects.phrase_origin_kind import (
        DecisionKind,
        OccurrenceOrigin,
        ShownBy,
    )
    from backend.domain.value_objects.word_status import WordStatus
    from backend.infrastructure.persistence.sqla_candidate_repository import (
        SqlaCandidateRepository,
    )
    from backend.infrastructure.persistence.sqla_occurrence_repository import (
        SqlaOccurrenceRepository,
    )

    words = SqlaCandidateRepository(session)
    occurrences = SqlaOccurrenceRepository(session)
    key = WordKey.of(word.lemma, word.is_phrasal_verb)
    word_id = next(
        (w.id for w in occurrences.word_rows(word.source_id) if w.key == key), None,
    )
    is_new = word_id is None
    if word_id is None:
        word_id = words.add_word(word)
    decided = is_new and word.status is not WordStatus.PENDING
    if decided:
        words.set_word_status(word_id, word.status)
    if origin is None:
        origin = (
            OccurrenceOrigin.EXAMPLE if position is None
            else OccurrenceOrigin.AUTO if is_new else OccurrenceOrigin.MANUAL
        )
    added = occurrences.add(Occurrence(
        candidate_id=word_id,
        origin=origin,
        source_phrase=text,
        phrase_position=position,
        key=None,
        fragment_score=None,
        shown_by=ShownBy.SELECTION if origin is OccurrenceOrigin.AUTO else ShownBy.USER,
        skipped=skipped,
        is_decision=decided,
        decision_kind=DecisionKind.LEARN if decided else None,
    ))
    assert added.id is not None
    return word_id, added.id


@dataclass
class SeedWord(StoredCandidate):
    """A word with one phrase to store with `store_cards`; `phrase_id` is set once stored."""

    source_phrase: Phrase | None = None
    phrase_position: DocumentPosition | None = None
    skipped: bool = False
    phrase_id: int | None = None


def store_cards(session: Session, words: list[SeedWord]) -> list[SeedWord]:
    """Each word's phrase through the repositories (see `store_card`), the words as stored."""
    stored: list[SeedWord] = []
    for word in words:
        assert word.source_phrase is not None
        word_id, phrase_id = store_card(
            session, word, word.source_phrase, position=word.phrase_position,
            skipped=word.skipped,
        )
        stored.append(replace(word, id=word_id, phrase_id=phrase_id))
    return stored
