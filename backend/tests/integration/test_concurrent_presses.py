"""Two presses at once on two phrases of one word (two requests, two sessions): the first
decides the word, the second finds it decided and is refused. A word never gets two
decision cards, and neither press fails on the database."""
from __future__ import annotations

import threading
from typing import TYPE_CHECKING

import pytest
from backend.domain.entities.occurrence import Occurrence
from backend.domain.exceptions import ActionRefusedError
from backend.domain.value_objects.candidate_section import CandidateSection
from backend.domain.value_objects.card_choice import Press, Refusal
from backend.domain.value_objects.cloze_hint_kind import ClozeHintKind
from backend.domain.value_objects.phrase_origin_kind import OccurrenceOrigin, ShownBy
from backend.infrastructure.persistence.database import Base, create_session_factory
from backend.infrastructure.persistence.session_change_recorder import SessionChangeRecorder
from backend.infrastructure.persistence.sqla_occurrence_repository import (
    SqlaOccurrenceRepository,
)
from sqlalchemy import text

from tests.decision_support import Decisions
from tests.integration.conftest import insert_source
from tests.phrase_support import phrase
from tests.word_support import insert_word, phrase_id_of

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

    from backend.domain.value_objects.card_choice import WordState
    from sqlalchemy.orm import Session, sessionmaker

pytestmark = pytest.mark.integration

WORD = 1
FIRST = phrase_id_of(WORD)
# How long the first press, having read the word, gives the second one to get ahead of it.
HEAD_START_S = 1.0
JOIN_S = 30.0


@pytest.fixture
def factory(tmp_path: Path) -> sessionmaker[Session]:
    sessions = create_session_factory(f"sqlite:///{tmp_path / 'app.db'}")
    bind = sessions.kw["bind"]
    Base.metadata.create_all(bind)
    return sessions


def _seed(factory: sessionmaker[Session]) -> int:
    """The word with two shown phrases: FIRST and the returned one."""
    with factory() as session:
        insert_source(session, 1)
        insert_word(session, WORD, lemma="glare", pos="VERB", phrase_text="He glared at me.")
        second = SqlaOccurrenceRepository(session, SessionChangeRecorder(session)).add(Occurrence(
            candidate_id=WORD, origin=OccurrenceOrigin.MANUAL,
            source_phrase=phrase("She glared back.", "glared"), phrase_position=None,
            key=None, fragment_score=None,
            earned_section=CandidateSection.READY, shown_by=ShownBy.USER,
        ))
        session.commit()
        assert second.id is not None
        return second.id


class _Race:
    """The first press reads the word, then waits for the second one to finish before it
    writes; if the first holds the database, the second cannot finish and the wait times
    out."""

    def __init__(self, factory: sessionmaker[Session]) -> None:
        self._factory = factory
        self._first_read = threading.Event()
        self._second_done = threading.Event()
        self.outcomes: dict[str, BaseException | None] = {}

    def run(self, first: Callable[[Decisions], None], second: Callable[[Decisions], None]) -> None:
        threads = [
            threading.Thread(target=self._first, args=(first,)),
            threading.Thread(target=self._second, args=(second,)),
        ]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(JOIN_S)

    def _first(self, act: Callable[[Decisions], None]) -> None:
        with self._factory() as session:
            decisions = Decisions(session)
            read = decisions.word_states.of_word

            def of_word_then_wait(word_id: int) -> WordState | None:
                state = read(word_id)
                if not self._first_read.is_set():
                    self._first_read.set()
                    self._second_done.wait(HEAD_START_S)
                return state

            decisions.word_states.of_word = of_word_then_wait  # type: ignore[method-assign]
            self.outcomes["first"] = self._act(session, decisions, act)

    def _second(self, act: Callable[[Decisions], None]) -> None:
        self._first_read.wait(JOIN_S)
        with self._factory() as session:
            self.outcomes["second"] = self._act(session, Decisions(session), act)
        self._second_done.set()

    @staticmethod
    def _act(
        session: Session, decisions: Decisions, act: Callable[[Decisions], None],
    ) -> BaseException | None:
        try:
            act(decisions)
            session.commit()
        except Exception as error:  # noqa: BLE001 — the outcome is what the test checks
            session.rollback()
            return error
        return None


def _decision_cards(factory: sessionmaker[Session]) -> list[tuple[int, str]]:
    with factory() as session:
        return [
            (int(row.id), str(row.choice)) for row in session.execute(text(
                "SELECT id, choice FROM phrases"
                " WHERE candidate_id = :w AND choice IN ('learn', 'cloze', 'known')"
            ), {"w": WORD})
        ]


def _assert_one_won(race: _Race, factory: sessionmaker[Session], winner: int) -> None:
    assert race.outcomes["first"] is None
    refused = race.outcomes["second"]
    assert isinstance(refused, ActionRefusedError), refused
    assert refused.refusal is Refusal.NOT_DECISION_CARD
    assert [card for card, _ in _decision_cards(factory)] == [winner]


@pytest.mark.parametrize(("first", "second"), [
    pytest.param(Press.LEARN, Press.LEARN, id="learn-and-learn"),
    pytest.param(Press.KNOWN, Press.LEARN, id="known-and-learn"),
])
def test_two_presses_on_two_phrases_decide_the_word_once(
    factory: sessionmaker[Session], first: Press, second: Press,
) -> None:
    sibling = _seed(factory)
    race = _Race(factory)

    race.run(
        lambda d: d.decide_phrase().decide(FIRST, first),
        lambda d: d.decide_phrase().decide(sibling, second),
    )

    _assert_one_won(race, factory, FIRST)


def test_a_cloze_saved_while_another_phrase_is_learned_decides_the_word_once(
    factory: sessionmaker[Session],
) -> None:
    sibling = _seed(factory)
    race = _Race(factory)

    race.run(
        lambda d: d.decide_phrase().decide(FIRST, Press.LEARN),
        lambda d: d.save_cloze().execute(
            sibling, "She glared back.", [1], ClozeHintKind.NONE, None,
        ),
    )

    _assert_one_won(race, factory, FIRST)


OTHER_WORD = 50
THERE = phrase_id_of(OTHER_WORD)


def _seed_in_another_source(factory: sessionmaker[Session]) -> None:
    """The lemma of WORD in source 2 too: card THERE."""
    with factory() as session:
        insert_source(session, 2)
        insert_word(session, OTHER_WORD, source_id=2, lemma="glare", pos="VERB",
                    phrase_text="She glared back.")
        session.commit()


def _assert_decided_elsewhere(race: _Race, factory: sessionmaker[Session]) -> None:
    assert race.outcomes["first"] is None
    refused = race.outcomes["second"]
    assert isinstance(refused, ActionRefusedError), refused
    assert refused.refusal is Refusal.DECIDED_ELSEWHERE
    with factory() as session:
        decided = session.execute(text(
            "SELECT count(*) FROM phrases WHERE choice IN ('learn', 'cloze', 'known')"
        )).scalar_one()
    assert decided == 1


def test_two_learns_on_one_lemma_in_two_sources_decide_it_once(
    factory: sessionmaker[Session],
) -> None:
    _seed(factory)
    _seed_in_another_source(factory)
    race = _Race(factory)

    race.run(
        lambda d: d.decide_phrase().decide(FIRST, Press.LEARN),
        lambda d: d.decide_phrase().decide(THERE, Press.LEARN),
    )

    _assert_decided_elsewhere(race, factory)


def test_a_press_reads_what_the_user_knows_once_it_holds_the_database(
    factory: sessionmaker[Session],
) -> None:
    """The second request read the lists before the first committed; its press reads
    them again."""
    _seed(factory)
    _seed_in_another_source(factory)
    race = _Race(factory)

    def read_then_learn(decisions: Decisions) -> None:
        decisions.vocabulary.of("glare")
        decisions.decide_phrase().decide(THERE, Press.LEARN)

    race.run(lambda d: d.decide_phrase().decide(FIRST, Press.LEARN), read_then_learn)

    _assert_decided_elsewhere(race, factory)


def test_the_database_holds_one_decision_card_per_word(factory: sessionmaker[Session]) -> None:
    sibling = _seed(factory)
    with factory() as session:
        session.execute(text("UPDATE phrases SET choice = 'learn' WHERE id = :id"), {"id": FIRST})
        with pytest.raises(Exception, match="UNIQUE constraint failed"):
            session.execute(
                text("UPDATE phrases SET choice = 'known' WHERE id = :id"), {"id": sibling},
            )
