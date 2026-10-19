"""Word states over a real database: the choices and active bindings read back as saved,
and the stored status is always the decision status."""
from __future__ import annotations

import itertools
from typing import TYPE_CHECKING
from unittest.mock import patch

import pytest
from backend.domain.value_objects.card_choice import (
    DECISION_CHOICES,
    Binding,
    CardChoice,
    CardState,
    NoteKind,
    decision_status,
)
from backend.infrastructure.persistence.sqla_word_state_repository import (
    SqlaWordStateRepository,
)
from sqlalchemy import text

from tests.decision_support import NOW
from tests.integration.conftest import insert_source
from tests.word_support import CREATED_AT, bind, insert_word, phrase_id_of

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

pytestmark = pytest.mark.integration

WORD = 1
FIRST = phrase_id_of(WORD)
SECOND = 5000
OTHER_SOURCE = 2


@pytest.fixture
def repo(db_session: Session, source_id: int) -> SqlaWordStateRepository:
    insert_word(db_session, WORD, source_id=source_id, lemma="Glare", pos="VERB")
    db_session.execute(
        text(
            "INSERT INTO phrases (id, candidate_id, source_phrase, origin, shown_by, choice,"
            " created_at, earned_section) SELECT :id, candidate_id, source_phrase, 'manual',"
            " 'user', 'none', created_at, earned_section FROM phrases WHERE id = :first"
        ),
        {"id": SECOND, "first": FIRST},
    )
    return SqlaWordStateRepository(db_session)


def _status(session: Session) -> str:
    return str(session.execute(
        text("SELECT status FROM candidates WHERE id = :id"), {"id": WORD},
    ).scalar_one())


def test_a_word_reads_its_cards_and_their_active_bindings(
    repo: SqlaWordStateRepository, db_session: Session,
) -> None:
    db_session.execute(text("UPDATE phrases SET choice = 'cloze' WHERE id = :id"), {"id": FIRST})
    bind(db_session, WORD, FIRST, kind="cloze")
    bind(db_session, WORD, SECOND, released_at=CREATED_AT)

    word = repo.of_word(WORD)

    assert word is not None
    assert (word.word_id, word.lemma, word.pos, word.source_id) == (WORD, "Glare", "VERB", 1)
    [first, second] = word.cards
    assert (first.card_id, first.choice) == (FIRST, CardChoice.CLOZE)
    assert first.binding is not None
    assert first.binding.note_kind is NoteKind.CLOZE
    assert (second.card_id, second.choice, second.binding) == (SECOND, CardChoice.NONE, None)


@pytest.mark.parametrize(
    ("first", "second"),
    [
        (a, b) for a, b in itertools.product(CardChoice, repeat=2)
        if not (a in DECISION_CHOICES and b in DECISION_CHOICES)
    ],
)
def test_save_round_trips_and_stores_the_decision_status(
    repo: SqlaWordStateRepository, db_session: Session, first: CardChoice, second: CardChoice,
) -> None:
    word = repo.of_word(WORD)
    assert word is not None
    changed = word.with_cards(CardState(FIRST, first), CardState(SECOND, second))

    repo.save(changed)

    assert repo.of_word(WORD) == changed
    assert _status(db_session) == decision_status(changed).value


def test_the_decision_moves_between_cards_in_one_save(
    repo: SqlaWordStateRepository,
) -> None:
    """The decision card is unique: the card that stops deciding is written first."""
    word = repo.of_word(WORD)
    assert word is not None
    repo.save(word.with_cards(CardState(FIRST, CardChoice.LEARN)))

    moved = word.with_cards(CardState(FIRST, CardChoice.NONE), CardState(SECOND, CardChoice.KNOWN))
    repo.save(moved)

    assert repo.of_word(WORD) == moved


def test_a_bound_learn_is_stored_learning(
    repo: SqlaWordStateRepository, db_session: Session,
) -> None:
    db_session.execute(text("UPDATE phrases SET choice = 'learn' WHERE id = :id"), {"id": FIRST})
    bind(db_session, WORD, FIRST)
    word = repo.of_word(WORD)
    assert word is not None

    repo.save(word)

    assert _status(db_session) == "learning"
    binding = word.card(FIRST).binding
    assert binding is not None
    assert binding == Binding(NoteKind.LEARN, binding.learning_since)
    assert binding.learning_since < NOW


def test_save_writes_the_cards_choice_onto_its_active_binding_only(
    repo: SqlaWordStateRepository, db_session: Session,
) -> None:
    """An orphan must still tell a Known card's binding from a Learn one's."""
    db_session.execute(text("UPDATE phrases SET choice = 'learn' WHERE id = :id"), {"id": FIRST})
    bind(db_session, WORD, FIRST, released_at=CREATED_AT)
    bind(db_session, WORD, FIRST)
    word = repo.of_word(WORD)
    assert word is not None

    repo.save(word.with_cards(CardState(FIRST, CardChoice.KNOWN, word.card(FIRST).binding)))

    rows = db_session.execute(text(
        "SELECT released_at IS NULL, card_choice FROM anki_synced_cards ORDER BY id"
    )).all()
    assert [tuple(row) for row in rows] == [(0, "learn"), (1, "known")]


def test_words_are_read_by_id(repo: SqlaWordStateRepository, db_session: Session) -> None:
    insert_word(db_session, 2, source_id=1, lemma="linger")
    insert_word(db_session, 3, source_id=1, lemma="drift")

    assert sorted(repo.of_words([WORD, 3])) == [WORD, 3]
    assert repo.of_words([]) == {}


def test_a_batch_of_saves_expires_the_session_once(
    repo: SqlaWordStateRepository, db_session: Session,
) -> None:
    insert_word(db_session, 2, source_id=1, lemma="linger")
    words = [repo.of_word(WORD), repo.of_word(2)]
    with patch.object(db_session, "expire_all", wraps=db_session.expire_all) as expire:
        with repo.batch():
            for word in words:
                assert word is not None
                repo.save(word)
            assert expire.call_count == 0
        assert expire.call_count == 1

        repo.save(words[0])  # type: ignore[arg-type]
        assert expire.call_count == 2


def test_every_word_of_the_lemma_in_every_source(
    repo: SqlaWordStateRepository, db_session: Session,
) -> None:
    insert_source(db_session, OTHER_SOURCE)
    insert_word(db_session, 50, source_id=OTHER_SOURCE, lemma="glare")
    insert_word(db_session, 60, source_id=OTHER_SOURCE, lemma="linger")

    assert sorted(w.word_id for w in repo.of_lemma("GLARE")) == [WORD, 50]
    assert sorted(repo.of_source(OTHER_SOURCE)) == [50, 60]


def test_the_container_gives_one_knowledge_scope_per_session(db_session: Session) -> None:
    """One per request and one per job: each has its own database session."""
    from backend.infrastructure.container import Container

    container = Container()
    scope = container.knowledge_scope(db_session)

    assert container.knowledge_scope(db_session) is scope
    assert container._user_vocabulary(db_session).scope is scope  # noqa: SLF001
    other = type(db_session)(bind=db_session.get_bind())
    try:
        assert container.knowledge_scope(other) is not scope
    finally:
        other.close()
