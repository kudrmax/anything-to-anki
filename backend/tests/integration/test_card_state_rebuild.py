"""The full rebuild of the card state projection equals the review's own computation, for
every card at every threshold step (spec §5, §6)."""
from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from backend.application.utils.card_state_differences import differences
from backend.domain.value_objects.candidate_section import CandidateSection
from backend.domain.value_objects.card_choice import DecisionStatus
from backend.domain.value_objects.learning_timer import known_on
from backend.domain.value_objects.user_knowledge import Newness
from sqlalchemy import text

from tests.card_state_support import (
    BASK,
    BASK_TWO,
    BROOD_SECOND_PHRASE,
    FRET,
    GLARE,
    GLEAM,
    HOVER,
    LINGER,
    OH,
    SHOWN_CARDS,
    SPARK,
    SPARK_EXPORTED,
    SPARK_TWO,
    live_states,
    make_container,
    memory_factory,
    seed,
    stored_states,
)
from tests.word_support import phrase_id_of

if TYPE_CHECKING:
    from collections.abc import Generator

    from backend.infrastructure.container import Container
    from sqlalchemy.orm import Session, sessionmaker

pytestmark = pytest.mark.integration


@pytest.fixture()
def factory() -> Generator[sessionmaker[Session], None, None]:
    yield from memory_factory()


@pytest.fixture()
def container(factory: sessionmaker[Session]) -> Container:
    return make_container(factory)


@pytest.fixture()
def seeded(factory: sessionmaker[Session], container: Container) -> Container:
    seed(factory)
    return container


def test_the_rebuild_equals_the_live_computation(
    seeded: Container, factory: sessionmaker[Session],
) -> None:
    seeded.rebuild_card_states()
    stored, live = stored_states(seeded, factory), live_states(seeded, factory)
    assert differences(stored, live) == []
    assert {c.row for c in stored.cards} == set(live.cards)
    assert set(stored.words) == set(live.words)
    assert set(stored.phrase_words) == set(live.phrase_words)


def test_the_world_covers_every_kind_of_card(
    seeded: Container, factory: sessionmaker[Session],
) -> None:
    """The comparison above means something: the cases it was built for are all there."""
    seeded.rebuild_card_states()
    stored = stored_states(seeded, factory)
    cards = {c.row.phrase_id: c.row for c in stored.cards}
    assert len(cards) == SHOWN_CARDS
    assert phrase_id_of(LINGER) not in cards
    assert cards[phrase_id_of(SPARK)].changes_at == known_on(SPARK_EXPORTED)
    assert cards[phrase_id_of(SPARK_TWO)].changes_at == known_on(SPARK_EXPORTED)
    assert cards[phrase_id_of(SPARK_TWO)].is_done
    assert cards[phrase_id_of(BASK)].changes_at is None
    assert cards[phrase_id_of(BASK_TWO)].is_done
    assert cards[phrase_id_of(GLEAM)].wants_generation
    assert cards[phrase_id_of(GLARE)].wants_generation
    assert not cards[phrase_id_of(FRET)].wants_generation
    assert cards[phrase_id_of(OH)].sections.at(None) is CandidateSection.PROBABLY_KNOWN
    assert len(set(cards[phrase_id_of(GLARE)].sections.sections)) > 1
    assert len(set(cards[BROOD_SECOND_PHRASE].new_counts.counts)) > 1
    newness = {(w.phrase_id, w.lemma): w.newness for w in stored.phrase_words}
    assert newness[(phrase_id_of(GLEAM), "spark")] is Newness.ALWAYS
    assert newness[(phrase_id_of(GLEAM), "lighthouse")] is Newness.NEVER
    assert newness[(phrase_id_of(HOVER), "ominous")] is Newness.ALWAYS
    assert newness[(phrase_id_of(HOVER), "towers")] is Newness.NEVER
    assert newness[(BROOD_SECOND_PHRASE, "news")] is Newness.IF_RARE
    statuses = {w.word_id: w.status for w in stored.words}
    assert statuses[SPARK] is DecisionStatus.LEARNING
    assert statuses[GLEAM] is DecisionStatus.LEARN
    assert statuses[LINGER] is DecisionStatus.NEW


def test_every_row_carries_the_one_revision_of_the_rebuild(
    seeded: Container, factory: sessionmaker[Session],
) -> None:
    seeded.rebuild_card_states()
    seeded.rebuild_card_states()
    stored = stored_states(seeded, factory)
    assert stored.revision == 2  # noqa: PLR2004 — two rebuilds
    assert {c.revision for c in stored.cards} == {2}


def test_a_card_gone_since_the_last_rebuild_stays_as_a_removed_row(
    seeded: Container, factory: sessionmaker[Session],
) -> None:
    seeded.rebuild_card_states()
    with factory() as session:
        session.execute(
            text("UPDATE phrases SET shown_by = NULL WHERE id = :p"), {"p": phrase_id_of(GLARE)},
        )
        session.commit()
    seeded.rebuild_card_states()
    stored = stored_states(seeded, factory)
    gone = next(c for c in stored.cards if c.row.phrase_id == phrase_id_of(GLARE))
    assert gone.removed
    assert gone.revision == stored.revision
    assert not any(w.phrase_id == phrase_id_of(GLARE) for w in stored.phrase_words)
    assert differences(stored, live_states(seeded, factory)) == []


def test_a_card_shown_again_comes_backlive_states(
    seeded: Container, factory: sessionmaker[Session],
) -> None:
    seeded.rebuild_card_states()
    with factory() as session:
        session.execute(
            text("UPDATE phrases SET shown_by = NULL WHERE id = :p"), {"p": phrase_id_of(OH)},
        )
        session.commit()
    seeded.rebuild_card_states()
    with factory() as session:
        session.execute(
            text("UPDATE phrases SET shown_by = 'selection' WHERE id = :p"),
            {"p": phrase_id_of(OH)},
        )
        session.commit()
    seeded.rebuild_card_states()
    stored = stored_states(seeded, factory)
    assert not next(c for c in stored.cards if c.row.phrase_id == phrase_id_of(OH)).removed
    assert differences(stored, live_states(seeded, factory)) == []


def test_an_empty_database_rebuilds_to_empty_tables(
    container: Container, factory: sessionmaker[Session],
) -> None:
    container.rebuild_card_states()
    stored = stored_states(container, factory)
    assert (stored.cards, stored.words, stored.phrase_words) == ((), (), ())
    assert stored.revision == 1
    assert differences(stored, live_states(container, factory)) == []


def test_a_stored_row_that_drifted_is_reported_with_its_columns(
    seeded: Container, factory: sessionmaker[Session],
) -> None:
    seeded.rebuild_card_states()
    with factory() as session:
        session.execute(
            text("UPDATE card_states SET is_done = 1, sections = 'VVVVVVVV' WHERE phrase_id = :p"),
            {"p": phrase_id_of(GLARE)},
        )
        session.execute(text("UPDATE word_states SET status = 'known' WHERE word_id = :w"),
                        {"w": FRET})
        session.execute(text("DELETE FROM phrase_words WHERE phrase_id = :p AND position = 0"),
                        {"p": phrase_id_of(HOVER)})
        session.commit()
    found = differences(stored_states(seeded, factory), live_states(seeded, factory))
    assert [(d.table, d.key, d.lemma) for d in found] == [
        ("card_states", f"phrase_id={phrase_id_of(GLARE)}", "glare"),
        ("word_states", f"word_id={FRET}", "fret"),
        ("phrase_words", f"phrase_id={phrase_id_of(HOVER)} position=0", "drones"),
    ]
    card = found[0]
    assert card.stored.startswith("is_done=True sections=")
    assert card.live.startswith("is_done=False sections=")
    assert (found[2].stored, found[2].live) == ("missing", "present")


def test_a_stored_word_status_that_disagrees_with_the_cards_is_reported(
    seeded: Container, factory: sessionmaker[Session],
) -> None:
    """The live side reads the status the word stores; the rebuild derives it from the
    word's cards. A stored copy that drifted shows up. (The card itself reads done on both
    sides: the export queue, a rule input, reads the stored status too.)"""
    with factory() as session:
        session.execute(text("UPDATE candidates SET status = 'learn' WHERE id = :w"),
                        {"w": GLARE})
        session.commit()
    seeded.rebuild_card_states()
    found = differences(stored_states(seeded, factory), live_states(seeded, factory))
    assert [(d.table, d.key, d.stored, d.live) for d in found] == [
        ("word_states", f"word_id={GLARE}", "status=<DecisionStatus.NEW: 'pending'>",
         "status=<DecisionStatus.LEARN: 'learn'>"),
    ]
