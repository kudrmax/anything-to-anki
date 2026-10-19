"""Words and their phrases straight in the database, for tests below the repositories."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from typing import TYPE_CHECKING

from backend.domain.value_objects.card_choice import CardChoice
from backend.infrastructure.persistence.models import dump_phrase
from sqlalchemy import text

from tests.decision_support import NOW
from tests.phrase_support import phrase

if TYPE_CHECKING:
    from backend.domain.entities.occurrence import Occurrence
    from backend.domain.entities.stored_candidate import StoredCandidate
    from backend.domain.value_objects.document_position import DocumentPosition
    from backend.domain.value_objects.phrase import Phrase
    from backend.domain.value_objects.phrase_origin_kind import OccurrenceOrigin
    from sqlalchemy.engine import Connection
    from sqlalchemy.orm import Session

CREATED_AT = "2026-01-01 00:00:00"
# The values of `insert_word`'s `status`: what candidates.status stores, and "skip".
PENDING, LEARN, KNOWN, SKIP = "pending", "learn", "known", "skip"
# Phrase ids of seeds start past this, so a phrase id never equals a word id.
PHRASE_ID_OFFSET = 1000


def phrase_id_of(word_id: int) -> int:
    """The id `insert_word` gives the phrase of the word."""
    return word_id + PHRASE_ID_OFFSET


def insert_word(
    db: Session | Connection,
    word_id: int,
    *,
    source_id: int = 1,
    lemma: str | None = None,
    status: str = PENDING,
    phrase_text: str | None = None,
    pos: str = "NOUN",
    zipf_frequency: float = 3.0,
    is_sweet_spot: bool = False,
) -> None:
    """A word with one shown phrase, `phrase_id_of(word_id)`.

    The lemma is `word<id>` unless given: lemmas of a source are unique. `status` may be
    "skip": the word is pending and its phrase is skipped.
    """
    lemma = lemma or f"word{word_id}"
    skipped = status == SKIP
    db.execute(
        text(
            "INSERT INTO candidates (id, source_id, lemma, pos, zipf_frequency, is_sweet_spot,"
            " occurrences, status, is_phrasal_verb)"
            " VALUES (:id, :source_id, :lemma, :pos, :zipf, :sweet, 1, :status, 0)"
        ),
        {
            "id": word_id, "source_id": source_id, "lemma": lemma, "pos": pos,
            "zipf": zipf_frequency, "sweet": is_sweet_spot,
            "status": PENDING if skipped else status,
        },
    )
    db.execute(
        text(
            "INSERT INTO phrases (id, candidate_id, source_phrase, origin, shown_by, choice,"
            " created_at)"
            " VALUES (:id, :word_id, :phrase, 'auto', 'selection', :choice, :created_at)"
        ),
        {
            "id": phrase_id_of(word_id),
            "word_id": word_id,
            "phrase": dump_phrase(phrase(phrase_text or lemma, lemma)),
            "choice": CHOICE_OF_STATUS.get(status, CardChoice.NONE).value,
            "created_at": CREATED_AT,
        },
    )


# The choice `insert_word` gives the word's phrase for the status it is given.
CHOICE_OF_STATUS = {
    SKIP: CardChoice.SKIP,
    LEARN: CardChoice.LEARN,
    KNOWN: CardChoice.KNOWN,
}


def bind(
    db: Session | Connection,
    word_id: int,
    phrase_id: int,
    *,
    note_id: int = 900,
    lemma: str | None = None,
    kind: str = "learn",
    since: str | None = None,
    released_at: str | None = None,
) -> None:
    """A binding of the phrase to an Anki note, exported a day before the tests' moment
    unless `since` says otherwise; active unless `released_at`. It records the phrase's
    decision, or the kind it was exported as; the word's status follows
    a binding of its Learn decision, as an export makes it."""
    if since is None:
        since = (NOW - timedelta(days=1)).replace(tzinfo=None).isoformat(sep=" ")
    db.execute(
        text(
            "INSERT INTO anki_synced_cards (candidate_id, phrase_id, anki_note_id, lemma, pos,"
            " note_kind, card_choice, learning_since, released_at)"
            " VALUES (:word, :phrase, :note, COALESCE(:lemma,"
            " (SELECT lemma FROM candidates WHERE id = :word)), 'NOUN', :kind,"
            " COALESCE((SELECT choice FROM phrases WHERE id = :phrase"
            " AND choice IN ('learn', 'cloze', 'known')), :kind), :since, :released)"
        ),
        {
            "word": word_id, "phrase": phrase_id, "note": note_id, "lemma": lemma,
            "kind": kind, "since": since, "released": released_at,
        },
    )
    if released_at is None:
        db.execute(
            text(
                "UPDATE candidates SET status = 'learning'"
                " WHERE id = :word AND status = 'learn'"
            ),
            {"word": word_id},
        )



@dataclass(frozen=True)
class CardSeed:
    """A word and one phrase of it, to store with `store_cards`."""

    word: StoredCandidate
    text: Phrase
    position: DocumentPosition | None = None
    skipped: bool = False


@dataclass(frozen=True)
class SeededCard:
    """A stored word and the phrase stored for it, both with their ids."""

    word: StoredCandidate
    phrase: Occurrence

    @property
    def word_id(self) -> int:
        assert self.word.id is not None
        return self.word.id

    @property
    def phrase_id(self) -> int:
        assert self.phrase.id is not None
        return self.phrase.id


def store_card(
    session: Session,
    word: StoredCandidate,
    text: Phrase,
    *,
    position: DocumentPosition | None = None,
    origin: OccurrenceOrigin | None = None,
    skipped: bool = False,
) -> SeededCard:
    """A phrase of the word through the repositories; the word is made when the source has
    none of its lemma. A decided word made here decides on this phrase.

    `origin` is `auto` for a new word's phrase with a place in the document, `example`
    without one, `manual` for another phrase of a word. Phrase ids start past
    `PHRASE_ID_OFFSET`, so a phrase id never equals a word id.
    """
    from backend.domain.entities.occurrence import Occurrence
    from backend.domain.value_objects.built_analysis import WordKey
    from backend.domain.value_objects.phrase_origin_kind import OccurrenceOrigin, ShownBy
    from backend.domain.value_objects.word_status import WordStatus
    from backend.infrastructure.persistence.sqla_candidate_repository import (
        SqlaCandidateRepository,
    )
    from backend.infrastructure.persistence.sqla_occurrence_repository import (
        SqlaOccurrenceRepository,
    )
    from backend.infrastructure.persistence.sqla_word_state_repository import (
        SqlaWordStateRepository,
    )

    _offset_phrase_ids(session)
    words = SqlaCandidateRepository(session)
    occurrences = SqlaOccurrenceRepository(session)
    key = WordKey.of(word.lemma, word.is_phrasal_verb)
    word_id = next(
        (w.id for w in occurrences.word_rows(word.source_id) if w.key == key), None,
    )
    is_new = word_id is None
    if word_id is None:
        word_id = words.add_word(word)
    decided = is_new and word.status is not WordStatus.NEW
    choice = (
        CardChoice.KNOWN if word.status is WordStatus.KNOWN else CardChoice.LEARN
    ) if decided else CardChoice.SKIP if skipped else CardChoice.NONE
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
        choice=choice,
    ))
    states = SqlaWordStateRepository(session)
    state = states.of_word(word_id)
    assert state is not None
    states.save(state)
    stored = words.get_by_id(word_id)
    assert stored is not None
    return SeededCard(word=stored, phrase=added)


def store_cards(session: Session, seeds: list[CardSeed]) -> list[SeededCard]:
    """Each seed through `store_card`, in order."""
    return [
        store_card(session, s.word, s.text, position=s.position, skipped=s.skipped)
        for s in seeds
    ]


def _offset_phrase_ids(session: Session) -> None:
    session.execute(text(
        "INSERT INTO sqlite_sequence (name, seq) SELECT 'phrases', :offset"
        " WHERE NOT EXISTS (SELECT 1 FROM sqlite_sequence WHERE name = 'phrases')"
    ), {"offset": PHRASE_ID_OFFSET})
    session.execute(text(
        "UPDATE sqlite_sequence SET seq = :offset WHERE name = 'phrases' AND seq < :offset"
    ), {"offset": PHRASE_ID_OFFSET})
