"""The full rebuild of the card state projection equals the review's own computation, for
every card at every threshold step (spec §5, §6)."""
from __future__ import annotations

from dataclasses import replace
from datetime import timedelta
from typing import TYPE_CHECKING

import pytest
from backend.application.utils.card_state_differences import differences
from backend.domain.value_objects.candidate_section import CandidateSection
from backend.domain.value_objects.card_choice import DecisionStatus
from backend.domain.value_objects.cefr_level import CEFRLevel
from backend.domain.value_objects.learning_timer import known_on
from backend.domain.value_objects.user_knowledge import Newness
from backend.infrastructure.container import Container
from backend.infrastructure.persistence.database import Base, _enable_sqlite_foreign_keys
from backend.infrastructure.persistence.models import dump_phrase
from sqlalchemy import StaticPool, create_engine, event, text
from sqlalchemy.orm import Session, sessionmaker

from tests.decision_support import NOW, FixedClock
from tests.integration.conftest import insert_source
from tests.phrase_support import phrase
from tests.word_marks_support import insert_known, insert_unknown
from tests.word_support import CREATED_AT, bind, phrase_id_of

if TYPE_CHECKING:
    from collections.abc import Generator
    from datetime import datetime

    from backend.domain.value_objects.card_state_rows import CardStates, StoredCardStates
    from backend.domain.value_objects.phrase import Phrase

pytestmark = pytest.mark.integration

ONE, TWO = 1, 2
GLARE, SPARK, SPARK_TWO, DWELL, FRET, BASK, BASK_TWO = 1, 2, 3, 4, 5, 6, 7
GLEAM, OH, HOVER, LINGER, BROOD = 8, 9, 10, 11, 12
BROOD_SECOND_PHRASE = 5000
SPARK_EXPORTED = NOW - timedelta(days=1)
BASK_EXPORTED = NOW - timedelta(days=40)
SHOWN_CARDS = 12


def _naive(moment: datetime) -> str:
    return moment.replace(tzinfo=None).isoformat(sep=" ")


def _with(shown: Phrase, **words: tuple[float, CEFRLevel]) -> Phrase:
    """The phrase with the zipf and level of the named words changed."""
    return replace(shown, words=tuple(
        replace(word, zipf=words[word.lemma][0], level=words[word.lemma][1])
        if word.lemma in words else word
        for word in shown.words
    ))


def _word(
    session: Session, word_id: int, source_id: int, lemma: str, shown: Phrase, *,
    status: str = "pending", choice: str = "none", pos: str = "VERB", zipf: float = 3.0,
    shown_by: str | None = "selection", earned: str = "ready",
) -> None:
    session.execute(
        text(
            "INSERT INTO candidates (id, source_id, lemma, pos, zipf_frequency, is_sweet_spot,"
            " occurrences, status, is_phrasal_verb)"
            " VALUES (:id, :source, :lemma, :pos, :zipf, 0, 1, :status, 0)"
        ),
        {
            "id": word_id, "source": source_id, "lemma": lemma, "pos": pos, "zipf": zipf,
            "status": status,
        },
    )
    _phrase(session, phrase_id_of(word_id), word_id, shown, choice, shown_by, earned)


def _phrase(
    session: Session, phrase_id: int, word_id: int, shown: Phrase, choice: str,
    shown_by: str | None, earned: str,
) -> None:
    session.execute(
        text(
            "INSERT INTO phrases (id, candidate_id, source_phrase, origin, shown_by, choice,"
            " created_at, earned_section)"
            " VALUES (:id, :word, :phrase, 'manual', :shown_by, :choice, :at, :earned)"
        ),
        {
            "id": phrase_id, "word": word_id, "phrase": dump_phrase(shown),
            "shown_by": shown_by, "choice": choice, "at": CREATED_AT, "earned": earned,
        },
    )


def _seed(session: Session) -> None:
    """Two sources sharing lemmas: an open word, Learn in Anki with its timer running or
    due, Known, Skip, a Cloze waiting for export, junk, other words new by rarity, marked
    Unknown, learned elsewhere or marked Known, a level that makes a word known, a word not
    shown, and a word with two shown phrases."""
    insert_source(session, ONE)
    insert_source(session, TWO)
    session.execute(text("INSERT INTO settings (key, value) VALUES ('cefr_level', 'B2')"))
    _word(session, GLARE, ONE, "glare", _with(
        phrase(
            "He glared at the ominous lighthouse", "glare",
            new=["ominous", "lighthouse"], lemmas={"glared": "glare"},
        ),
        ominous=(3.2, CEFRLevel.C2), lighthouse=(4.2, CEFRLevel.C1),
    ))
    _word(session, SPARK, ONE, "spark", phrase("A spark flew", "spark"),
          status="learning", choice="learn", zipf=4.0)
    bind(session, SPARK, phrase_id_of(SPARK), note_id=901, since=_naive(SPARK_EXPORTED))
    _word(session, SPARK_TWO, TWO, "spark", phrase("The spark died", "spark"), zipf=4.0)
    _word(session, DWELL, ONE, "dwell", phrase(
        "They dwell in ominous caves", "dwell", new=["ominous", "caves"],
    ), status="known", choice="known")
    _word(session, FRET, TWO, "fret", phrase("Do not fret", "fret"), choice="skip")
    _word(session, BASK, ONE, "bask", phrase("Cats bask", "bask"),
          status="learning", choice="learn", zipf=2.8)
    bind(session, BASK, phrase_id_of(BASK), note_id=902, since=_naive(BASK_EXPORTED))
    _word(session, BASK_TWO, TWO, "bask", phrase("We bask in sun", "bask"), zipf=2.8)
    _word(session, GLEAM, TWO, "gleam", phrase(
        "Stars gleam over the spark and the lighthouse", "gleam", new=["lighthouse"],
    ), status="learn", choice="cloze", zipf=3.4)
    _word(session, OH, ONE, "oh", phrase("Oh no", "oh"), pos="INTJ", zipf=5.0)
    _word(session, HOVER, TWO, "hover", _with(
        phrase("Drones hover above ominous towers", "hover", new=["ominous", "towers"]),
        towers=(3.7, CEFRLevel.B2),
    ), earned="extra", zipf=3.6)
    _word(session, LINGER, ONE, "linger", phrase("Smells linger", "linger"), shown_by=None)
    _word(session, BROOD, TWO, "brood", phrase(
        "Hens brood quietly", "brood", new=["quietly"],
    ), zipf=2.4)
    _phrase(
        session, BROOD_SECOND_PHRASE, BROOD, _with(
            phrase("They brood over ominous news", "brood", new=["ominous", "news"]),
            news=(5.2, CEFRLevel.C1),
        ), "none", "selection", "probably_known",
    )
    insert_known(session, "lighthouse")
    insert_unknown(session, "ominous")
    session.commit()


@pytest.fixture()
def factory() -> Generator[sessionmaker[Session], None, None]:
    engine = create_engine(
        "sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool,
    )
    event.listen(engine, "connect", _enable_sqlite_foreign_keys)
    Base.metadata.create_all(engine)
    yield sessionmaker(bind=engine)
    engine.dispose()


@pytest.fixture()
def container(factory: sessionmaker[Session]) -> Container:
    return Container(session_factory=factory, clock=FixedClock(NOW))


@pytest.fixture()
def seeded(factory: sessionmaker[Session], container: Container) -> Container:
    with factory() as session:
        _seed(session)
    return container


def _stored(container: Container, factory: sessionmaker[Session]) -> StoredCardStates:
    with factory() as session:
        return container.card_state_projector(session).stored()


def _live(container: Container, factory: sessionmaker[Session]) -> CardStates:
    with factory() as session:
        return container.live_card_states(session).compute()


def test_the_rebuild_equals_the_live_computation(
    seeded: Container, factory: sessionmaker[Session],
) -> None:
    seeded.rebuild_card_states()
    stored, live = _stored(seeded, factory), _live(seeded, factory)
    assert differences(stored, live) == []
    assert {c.row for c in stored.cards} == set(live.cards)
    assert set(stored.words) == set(live.words)
    assert set(stored.phrase_words) == set(live.phrase_words)


def test_the_world_covers_every_kind_of_card(
    seeded: Container, factory: sessionmaker[Session],
) -> None:
    """The comparison above means something: the cases it was built for are all there."""
    seeded.rebuild_card_states()
    stored = _stored(seeded, factory)
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
    stored = _stored(seeded, factory)
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
    stored = _stored(seeded, factory)
    gone = next(c for c in stored.cards if c.row.phrase_id == phrase_id_of(GLARE))
    assert gone.removed
    assert gone.revision == stored.revision
    assert not any(w.phrase_id == phrase_id_of(GLARE) for w in stored.phrase_words)
    assert differences(stored, _live(seeded, factory)) == []


def test_a_card_shown_again_comes_back_live(
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
    stored = _stored(seeded, factory)
    assert not next(c for c in stored.cards if c.row.phrase_id == phrase_id_of(OH)).removed
    assert differences(stored, _live(seeded, factory)) == []


def test_an_empty_database_rebuilds_to_empty_tables(
    container: Container, factory: sessionmaker[Session],
) -> None:
    container.rebuild_card_states()
    stored = _stored(container, factory)
    assert (stored.cards, stored.words, stored.phrase_words) == ((), (), ())
    assert stored.revision == 1
    assert differences(stored, _live(container, factory)) == []


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
    found = differences(_stored(seeded, factory), _live(seeded, factory))
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
    found = differences(_stored(seeded, factory), _live(seeded, factory))
    assert [(d.table, d.key, d.stored, d.live) for d in found] == [
        ("word_states", f"word_id={GLARE}", "status=<DecisionStatus.NEW: 'pending'>",
         "status=<DecisionStatus.LEARN: 'learn'>"),
    ]
