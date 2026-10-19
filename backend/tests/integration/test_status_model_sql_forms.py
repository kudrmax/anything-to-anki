"""The SQL forms of the status model's predicates select exactly the words and cards the
predicates say, over words stored in every shape the decision tables allow."""
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import pytest
from backend.domain.services.card_view import chosen_to_learn, in_export_queue
from backend.domain.value_objects.card_choice import CardChoice, CardState, NoteKind, is_skipped
from backend.domain.value_objects.lemma_knowledge import LemmaKnowledge
from backend.infrastructure.persistence.models import PhraseModel, StoredCandidateModel
from backend.infrastructure.persistence.sqla_candidate_repository import SqlaCandidateRepository
from backend.infrastructure.persistence.sqla_card_query import SqlaCardQuery
from backend.infrastructure.persistence.sqla_learning_query import SqlaLearningQuery
from backend.infrastructure.persistence.sqla_word_state_repository import (
    SqlaWordStateRepository,
)
from sqlalchemy import select, text

from tests.decision_support import NOW
from tests.integration.conftest import insert_source
from tests.word_support import bind, insert_word, phrase_id_of

if TYPE_CHECKING:
    from backend.domain.value_objects.card_choice import WordState
    from sqlalchemy import ColumnElement
    from sqlalchemy.orm import Session

pytestmark = pytest.mark.integration

OTHER_SOURCE = 2
SECOND_PHRASE_OFFSET = 5000
NOTHING_KNOWN = LemmaKnowledge.at(
    NOW, known_marked=False, unknown=False, learn_anywhere=False, active_since=(),
)
LISTED_KNOWN = LemmaKnowledge.at(
    NOW, known_marked=True, unknown=False, learn_anywhere=False, active_since=(),
)


@dataclass(frozen=True)
class Shape:
    """A word's cards: the choice of each, and the note kind its active binding has."""

    cards: tuple[tuple[CardChoice, NoteKind | None], ...]
    source_id: int = 1


SHAPES = (
    Shape(((CardChoice.NONE, None),)),
    Shape(((CardChoice.SKIP, None),)),
    Shape(((CardChoice.LEARN, None),)),
    Shape(((CardChoice.CLOZE, None),)),
    Shape(((CardChoice.KNOWN, None),)),
    Shape(((CardChoice.LEARN, NoteKind.LEARN),)),
    Shape(((CardChoice.CLOZE, NoteKind.CLOZE),)),
    Shape(((CardChoice.KNOWN, NoteKind.LEARN),)),
    Shape(((CardChoice.NONE, None), (CardChoice.LEARN, None))),
    Shape(((CardChoice.SKIP, None), (CardChoice.KNOWN, None))),
    Shape(((CardChoice.LEARN, NoteKind.LEARN), (CardChoice.SKIP, None))),
    Shape(((CardChoice.SKIP, None), (CardChoice.NONE, None))),
    Shape(((CardChoice.LEARN, None),), source_id=OTHER_SOURCE),
    Shape(((CardChoice.CLOZE, NoteKind.CLOZE),), source_id=OTHER_SOURCE),
)


def _second_phrase(session: Session, word_id: int) -> int:
    phrase_id = SECOND_PHRASE_OFFSET + word_id
    session.execute(
        text(
            "INSERT INTO phrases (id, candidate_id, source_phrase, origin, shown_by, choice,"
            " created_at) SELECT :id, candidate_id, source_phrase, 'manual', 'user', 'none',"
            " created_at FROM phrases WHERE id = :first"
        ),
        {"id": phrase_id, "first": phrase_id_of(word_id)},
    )
    return phrase_id


def _store(session: Session, word_id: int, shape: Shape) -> WordState:
    words = SqlaWordStateRepository(session)
    insert_word(session, word_id, source_id=shape.source_id)
    ids = [phrase_id_of(word_id)] + [_second_phrase(session, word_id) for _ in shape.cards[1:]]
    stored = words.of_word(word_id)
    assert stored is not None
    choices = [choice for choice, _ in shape.cards]
    words.save(stored.with_cards(
        *(CardState(card_id, choice) for card_id, choice in zip(ids, choices, strict=True)),
    ))
    for card_id, (_, kind) in zip(ids, shape.cards, strict=True):
        if kind is not None:
            bind(session, word_id, card_id, note_id=word_id, kind=kind.value)
    bound = words.of_word(word_id)
    assert bound is not None
    words.save(bound)  # the stored decision status follows the bindings, as an export does
    return bound


@pytest.fixture
def words(db_session: Session, source_id: int) -> dict[int, WordState]:
    insert_source(db_session, OTHER_SOURCE)
    return {
        word_id: _store(db_session, word_id, shape)
        for word_id, shape in enumerate(SHAPES, start=1)
    }


def _word_ids(session: Session, where: ColumnElement[bool]) -> set[int]:
    return set(session.scalars(select(StoredCandidateModel.id).where(where)))


def test_the_stored_shapes_are_the_ones_meant(words: dict[int, WordState]) -> None:
    assert [
        tuple((card.choice, card.note) for card in words[word_id].cards)
        for word_id in sorted(words)
    ] == [shape.cards for shape in SHAPES]


def test_chosen_to_learn_in_sql_is_the_predicate(
    db_session: Session, words: dict[int, WordState],
) -> None:
    expected = {word_id for word_id, word in words.items() if chosen_to_learn(word)}
    assert expected  # the fixtures hold words of both kinds
    assert expected != set(words)

    assert _word_ids(db_session, StoredCandidateModel.chosen_to_learn()) == expected
    candidates = SqlaCandidateRepository(db_session)
    assert candidates.count_chosen_to_learn() == len(expected)
    assert {w.id for w in candidates.chosen_to_learn()} == expected
    assert {w.id for w in candidates.chosen_to_learn([OTHER_SOURCE])} == {
        word_id for word_id in expected if words[word_id].source_id == OTHER_SOURCE
    }
    by_source = SqlaCardQuery(db_session).learn_counts([1, OTHER_SOURCE])
    assert by_source == {
        source: sum(1 for word_id in expected if words[word_id].source_id == source)
        for source in (1, OTHER_SOURCE)
    }


def test_in_export_queue_in_sql_is_the_predicate(
    db_session: Session, words: dict[int, WordState],
) -> None:
    expected = {
        word_id for word_id, word in words.items()
        if in_export_queue(word, NOTHING_KNOWN, NOW)
    }
    assert expected

    assert _word_ids(db_session, StoredCandidateModel.in_export_queue()) == expected
    assert SqlaLearningQuery(db_session).awaiting_export() == {
        words[word_id].lemma for word_id in expected
    }


def test_a_learn_listed_known_since_leaves_the_queue_only_by_its_knowledge(
    db_session: Session, words: dict[int, WordState],
) -> None:
    """Q15 is knowledge, not stored: the SQL form selects the Learn words, and the
    predicate drops those whose lemma is in Known."""
    stored = _word_ids(db_session, StoredCandidateModel.in_export_queue())

    assert {
        word_id for word_id, word in words.items() if in_export_queue(word, LISTED_KNOWN, NOW)
    } == set()
    assert stored == {
        word_id for word_id, word in words.items()
        if in_export_queue(word, NOTHING_KNOWN, NOW)
    }


def test_the_card_predicates_in_sql_are_the_card_predicates(
    db_session: Session, words: dict[int, WordState],
) -> None:
    cards = [card for word in words.values() for card in word.cards]

    def phrase_ids(where: ColumnElement[bool]) -> set[int]:
        return set(db_session.scalars(select(PhraseModel.id).where(where)))

    assert phrase_ids(PhraseModel.is_decision()) == {c.card_id for c in cards if c.is_decision}
    assert phrase_ids(PhraseModel.is_skipped()) == {c.card_id for c in cards if is_skipped(c)}
