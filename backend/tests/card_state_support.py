"""A world of two sources sharing lemmas for the card state projection tests, and the
stored and live rows of it."""
from __future__ import annotations

from dataclasses import replace
from datetime import timedelta
from typing import TYPE_CHECKING

from backend.domain.value_objects.cefr_level import CEFRLevel
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

ONE, TWO = 1, 2
GLARE, SPARK, SPARK_TWO, DWELL, FRET, BASK, BASK_TWO = 1, 2, 3, 4, 5, 6, 7
GLEAM, OH, HOVER, LINGER, BROOD = 8, 9, 10, 11, 12
BROOD_SECOND_PHRASE = 5000
SPARK_EXPORTED = NOW - timedelta(days=1)
BASK_EXPORTED = NOW - timedelta(days=40)
SHOWN_CARDS = 12


def naive(moment: datetime) -> str:
    return moment.replace(tzinfo=None).isoformat(sep=" ")


def with_levels(shown: Phrase, **words: tuple[float, CEFRLevel]) -> Phrase:
    """The phrase with the zipf and level of the named words changed."""
    return replace(shown, words=tuple(
        replace(word, zipf=words[word.lemma][0], level=words[word.lemma][1])
        if word.lemma in words else word
        for word in shown.words
    ))


def insert_card_word(
    session: Session, word_id: int, source_id: int, lemma: str, shown: Phrase, *,
    choice: str = "none", pos: str = "VERB", zipf: float = 3.0,
    shown_by: str | None = "selection", earned: str = "ready",
) -> None:
    session.execute(
        text(
            "INSERT INTO candidates (id, source_id, lemma, pos, zipf_frequency, is_sweet_spot,"
            " occurrences, is_phrasal_verb)"
            " VALUES (:id, :source, :lemma, :pos, :zipf, 0, 1, 0)"
        ),
        {"id": word_id, "source": source_id, "lemma": lemma, "pos": pos, "zipf": zipf},
    )
    insert_card_phrase(session, phrase_id_of(word_id), word_id, shown, choice, shown_by, earned)


def insert_card_phrase(
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


def seed_world(session: Session) -> None:
    """Two sources sharing lemmas: an open word, Learn in Anki with its timer running or
    due, Known, Skip, a Cloze waiting for export, junk, other words new by rarity, marked
    Unknown, learned elsewhere or marked Known, a level that makes a word known, a word not
    shown, and a word with two shown phrases."""
    insert_source(session, ONE)
    insert_source(session, TWO)
    session.execute(text("INSERT INTO settings (key, value) VALUES ('cefr_level', 'B2')"))
    insert_card_word(session, GLARE, ONE, "glare", with_levels(
        phrase(
            "He glared at the ominous lighthouse", "glare",
            new=["ominous", "lighthouse"], lemmas={"glared": "glare"},
        ),
        ominous=(3.2, CEFRLevel.C2), lighthouse=(4.2, CEFRLevel.C1),
    ))
    insert_card_word(session, SPARK, ONE, "spark", phrase("A spark flew", "spark"),
          choice="learn", zipf=4.0)
    bind(session, SPARK, phrase_id_of(SPARK), note_id=901, since=naive(SPARK_EXPORTED))
    insert_card_word(
        session, SPARK_TWO, TWO, "spark", phrase("The spark died", "spark"), zipf=4.0,
    )
    insert_card_word(session, DWELL, ONE, "dwell", phrase(
        "They dwell in ominous caves", "dwell", new=["ominous", "caves"],
    ), choice="known")
    insert_card_word(
        session, FRET, TWO, "fret", phrase("Do not fret", "fret"), choice="skip",
    )
    insert_card_word(session, BASK, ONE, "bask", phrase("Cats bask", "bask"),
          choice="learn", zipf=2.8)
    bind(session, BASK, phrase_id_of(BASK), note_id=902, since=naive(BASK_EXPORTED))
    insert_card_word(
        session, BASK_TWO, TWO, "bask", phrase("We bask in sun", "bask"), zipf=2.8,
    )
    insert_card_word(session, GLEAM, TWO, "gleam", phrase(
        "Stars gleam over the spark and the lighthouse", "gleam", new=["lighthouse"],
    ), choice="cloze", zipf=3.4)
    insert_card_word(session, OH, ONE, "oh", phrase("Oh no", "oh"), pos="INTJ", zipf=5.0)
    insert_card_word(session, HOVER, TWO, "hover", with_levels(
        phrase("Drones hover above ominous towers", "hover", new=["ominous", "towers"]),
        towers=(3.7, CEFRLevel.B2),
    ), earned="extra", zipf=3.6)
    insert_card_word(
        session, LINGER, ONE, "linger", phrase("Smells linger", "linger"), shown_by=None,
    )
    insert_card_word(session, BROOD, TWO, "brood", phrase(
        "Hens brood quietly", "brood", new=["quietly"],
    ), zipf=2.4)
    insert_card_phrase(
        session, BROOD_SECOND_PHRASE, BROOD, with_levels(
            phrase("They brood over ominous news", "brood", new=["ominous", "news"]),
            news=(5.2, CEFRLevel.C1),
        ), "none", "selection", "probably_known",
    )
    insert_known(session, "lighthouse")
    insert_unknown(session, "ominous")
    session.commit()


def memory_factory() -> Generator[sessionmaker[Session], None, None]:
    """Sessions on one in-memory database made from the models."""
    engine = create_engine(
        "sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool,
    )
    event.listen(engine, "connect", _enable_sqlite_foreign_keys)
    Base.metadata.create_all(engine)
    yield sessionmaker(bind=engine)
    engine.dispose()


def make_container(factory: sessionmaker[Session]) -> Container:
    return Container(session_factory=factory, clock=FixedClock(NOW))


def seed(factory: sessionmaker[Session]) -> None:
    with factory() as session:
        seed_world(session)


def stored_states(container: Container, factory: sessionmaker[Session]) -> StoredCardStates:
    with factory() as session:
        return container.card_state_projector(session).stored()


def live_states(container: Container, factory: sessionmaker[Session]) -> CardStates:
    with factory() as session:
        return container.live_card_states(session).compute()


