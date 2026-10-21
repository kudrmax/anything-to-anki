"""Time changes the card state by an explicit write: the tick recomputes the lemmas whose
Anki timer came due, those of a card row and those of a binding no card holds any more
(spec §5)."""
from __future__ import annotations

from datetime import timedelta
from typing import TYPE_CHECKING

import pytest
from backend.application.utils.card_state_differences import differences
from backend.domain.value_objects.learning_timer import LEARNING_KNOWN_AFTER, known_on
from backend.infrastructure.container import Container
from backend.infrastructure.persistence.sqla_card_state_store import SqlaCardStateStore
from sqlalchemy import text

from tests.card_state_support import (
    HOVER,
    SPARK,
    SPARK_EXPORTED,
    SPARK_TWO,
    live_states,
    memory_factory,
    naive,
    seed,
    stored_states,
)
from tests.decision_support import NOW, FixedClock
from tests.word_support import phrase_id_of

if TYPE_CHECKING:
    from collections.abc import Generator
    from datetime import datetime

    from sqlalchemy.orm import Session, sessionmaker

pytestmark = pytest.mark.integration

A_MINUTE = timedelta(minutes=1)
# "towers" stands in HOVER's phrase only, as an other word.
TOWERS = "towers"
TOWERS_EXPORTED = NOW - LEARNING_KNOWN_AFTER + timedelta(days=2)


@pytest.fixture()
def factory() -> Generator[sessionmaker[Session], None, None]:
    yield from memory_factory()


class Clocked:
    """The seeded world on a clock the test moves."""

    def __init__(self, factory: sessionmaker[Session]) -> None:
        seed(factory)
        self.factory = factory
        self.clock = FixedClock(NOW)
        self.container = Container(session_factory=factory, clock=self.clock)
        self.container.rebuild_card_states()

    def at(self, moment: datetime) -> None:
        self.clock.moment = moment

    def differences(self) -> list[str]:
        return [
            str(d) for d in differences(
                stored_states(self.container, self.factory),
                live_states(self.container, self.factory),
            )
        ]

    def changes_at(self, phrase_id: int) -> datetime | None:
        stored = stored_states(self.container, self.factory)
        return next(c for c in stored.cards if c.row.phrase_id == phrase_id).row.changes_at

    def ticked_at(self) -> datetime | None:
        with self.factory() as session:
            return SqlaCardStateStore(session).ticked_at()


@pytest.fixture()
def world(factory: sessionmaker[Session]) -> Clocked:
    return Clocked(factory)


def test_a_timer_coming_due_is_written_by_the_tick(world: Clocked) -> None:
    due = known_on(SPARK_EXPORTED)
    assert world.changes_at(phrase_id_of(SPARK)) == due
    world.at(due + A_MINUTE)
    assert world.differences()  # the stored rows still read as before the timer

    world.container.tick_card_states()

    assert world.differences() == []
    assert world.changes_at(phrase_id_of(SPARK)) is None
    assert world.changes_at(phrase_id_of(SPARK_TWO)) is None


def test_a_tick_before_any_timer_changes_nothing(world: Clocked) -> None:
    before = stored_states(world.container, world.factory)
    world.at(NOW + A_MINUTE)

    world.container.tick_card_states()

    after = stored_states(world.container, world.factory)
    assert after.revision == before.revision
    assert world.differences() == []
    assert world.ticked_at() == NOW + A_MINUTE


def test_the_rebuild_is_up_to_date_with_time_as_of_its_moment(world: Clocked) -> None:
    assert world.ticked_at() == NOW


def test_a_binding_no_card_holds_still_comes_due_in_the_phrases_holding_its_lemma(
    world: Clocked,
) -> None:
    """An orphan binding of "towers": no card row carries its timer, yet HOVER's phrase
    holds the lemma as an other word, new while it is learned and known once it is due."""
    with world.factory() as session:
        session.execute(
            text(
                "INSERT INTO anki_synced_cards (candidate_id, phrase_id, anki_note_id, lemma,"
                " pos, note_kind, learning_since) VALUES (NULL, NULL, 990, :lemma, 'NOUN',"
                " 'learn', :since)"
            ),
            {"lemma": TOWERS, "since": naive(TOWERS_EXPORTED)},
        )
        session.commit()
    world.container.rebuild_card_states()
    assert world.differences() == []
    hover = phrase_id_of(HOVER)
    before = next(
        c.row for c in stored_states(world.container, world.factory).cards
        if c.row.phrase_id == hover
    )
    world.at(known_on(TOWERS_EXPORTED) + A_MINUTE)
    assert any(f"phrase_id={hover}" in d for d in world.differences())

    world.container.tick_card_states()

    assert world.differences() == []
    after = next(
        c.row for c in stored_states(world.container, world.factory).cards
        if c.row.phrase_id == hover
    )
    assert after.new_counts != before.new_counts


def test_a_tick_takes_each_binding_once(world: Clocked) -> None:
    """A binding due before the last tick is not done again: only the cards of a timer due
    since then move."""
    world.at(known_on(SPARK_EXPORTED) + A_MINUTE)
    world.container.tick_card_states()
    after_first = stored_states(world.container, world.factory)
    world.at(known_on(SPARK_EXPORTED) + 2 * A_MINUTE)

    world.container.tick_card_states()

    assert stored_states(world.container, world.factory).revision == after_first.revision
    assert world.differences() == []
