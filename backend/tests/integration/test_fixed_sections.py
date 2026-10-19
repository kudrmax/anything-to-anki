"""A card stands in the section its phrase earned when it was added or its text last changed,
whatever the user knows, learns or sets afterwards."""
from __future__ import annotations

from collections.abc import Generator  # noqa: TC003
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any

import pytest
from backend.application.utils.generation_targets import GenerationCard, ReadyCards
from backend.infrastructure.api.app import app
from backend.infrastructure.api.dependencies import get_db_session, get_session_factory
from backend.infrastructure.persistence.database import (
    Base,
    _enable_sqlite_foreign_keys,
)
from backend.infrastructure.persistence.models import WordDecisionModel, dump_phrase
from backend.infrastructure.persistence.sqla_candidate_repository import SqlaCandidateRepository
from backend.infrastructure.persistence.sqla_known_word_repository import (
    SqlaKnownWordRepository,
)
from backend.infrastructure.persistence.sqla_occurrence_repository import (
    SqlaOccurrenceRepository,
)
from backend.infrastructure.persistence.sqla_settings_repository import SqlaSettingsRepository
from fastapi.testclient import TestClient
from sqlalchemy import StaticPool, create_engine, event, text
from sqlalchemy.orm import Session, sessionmaker

from tests.integration.conftest import insert_source
from tests.phrase_support import phrase
from tests.word_support import bind, insert_word, phrase_id_of

if TYPE_CHECKING:
    from collections.abc import Callable

    from backend.domain.value_objects.phrase import Phrase

pytestmark = pytest.mark.integration

Json = Any

SOURCE = 1
EMBER, ZEPHYR = 1, 2
EMBER_PHRASE = phrase_id_of(EMBER)
EMBER_ZIPF = 4.2
LONG_AGO = datetime.now(tz=UTC) - timedelta(days=60)
SINCE_FORMAT = "%Y-%m-%d %H:%M:%S"


def _store_phrase(session: Session, phrase_id: int, text_: Phrase, section: str) -> None:
    session.execute(
        text("UPDATE phrases SET source_phrase = :p, earned_section = :s WHERE id = :id"),
        {"p": dump_phrase(text_), "s": section, "id": phrase_id},
    )


@pytest.fixture()
def factory() -> Generator[sessionmaker[Session], None, None]:
    engine = create_engine(
        "sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool,
    )
    event.listen(engine, "connect", _enable_sqlite_foreign_keys)
    Base.metadata.create_all(engine)
    made = sessionmaker(bind=engine)
    with made() as session:
        insert_source(session, SOURCE)
        insert_word(session, EMBER, lemma="ember", zipf_frequency=EMBER_ZIPF)
        _store_phrase(
            session, EMBER_PHRASE, phrase("an ember zephyr", "ember", new=("zephyr",)), "extra",
        )
        insert_word(session, ZEPHYR, lemma="zephyr", status="learn")
        bind(session, ZEPHYR, phrase_id_of(ZEPHYR))
        session.commit()
    yield made
    engine.dispose()


@pytest.fixture()
def client(factory: sessionmaker[Session]) -> Generator[TestClient, None, None]:
    def override_session() -> Generator[Session, None, None]:
        with factory() as session:
            yield session

    app.dependency_overrides[get_db_session] = override_session
    app.dependency_overrides[get_session_factory] = lambda: factory
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def _listing(client: TestClient) -> Json:
    source = client.get(f"/sources/{SOURCE}").json()
    card = next(c for c in source["candidates"] if c["phrase_id"] == EMBER_PHRASE)
    return card["section"], source["progress"]


def _known_zephyr(session: Session) -> None:
    SqlaKnownWordRepository(session).add("zephyr", None)


def _learning_timer_expired(session: Session) -> None:
    session.execute(
        text("UPDATE anki_synced_cards SET learning_since = :since WHERE phrase_id = :id"),
        {"since": LONG_AGO.strftime(SINCE_FORMAT), "id": phrase_id_of(ZEPHYR)},
    )


def _calibration(session: Session) -> None:
    for i in range(4):
        session.add(WordDecisionModel(lemma=f"calibrated{i}", zipf_frequency=4.1, is_known=True))


def _threshold_setting(session: Session) -> None:
    SqlaSettingsRepository(session).set("frequent_word_threshold", "4.0")


def _cefr_level_setting(session: Session) -> None:
    SqlaSettingsRepository(session).set("cefr_level", "C2")


@pytest.mark.parametrize("change", [
    _known_zephyr, _learning_timer_expired, _calibration, _threshold_setting,
    _cefr_level_setting,
], ids=lambda f: f.__name__.lstrip("_"))
def test_an_open_card_keeps_its_section(
    client: TestClient, factory: sessionmaker[Session], change: Callable[[Session], None],
) -> None:
    before = _listing(client)
    assert before[0] == "extra"

    with factory() as session:
        change(session)
        session.commit()

    assert _listing(client) == before


def test_removing_known_puts_a_done_card_back_into_its_stored_section(
    client: TestClient,
) -> None:
    decided = client.post(f"/phrases/{EMBER_PHRASE}/decision", json={"button": "known"})
    assert decided.status_code == 200
    assert _listing(client)[0] == "reviewed"

    [entry] = [w for w in client.get("/known-words").json() if w["lemma"] == "ember"]
    assert client.delete(f"/known-words/{entry['removal_key']}").status_code == 200

    assert _listing(client)[0] == "extra"


def test_ready_generation_takes_cards_by_stored_section(
    factory: sessionmaker[Session],
) -> None:
    ready_id, extra_id = 10, 11
    with factory() as session:
        insert_word(session, ready_id, lemma="glare")
        _store_phrase(
            session, phrase_id_of(ready_id), phrase("a glare zephyr", "glare", new=("zephyr",)),
            "ready",
        )
        insert_word(session, extra_id, lemma="spark")
        _store_phrase(session, phrase_id_of(extra_id), phrase("a spark here", "spark"), "extra")
        session.commit()

        words = SqlaCandidateRepository(session)
        phrases = SqlaOccurrenceRepository(session)
        cards = []
        for word_id in (ready_id, extra_id):
            word = words.get_by_id(word_id)
            occurrence = phrases.get(phrase_id_of(word_id))
            assert word is not None and occurrence is not None
            cards.append(GenerationCard(word, occurrence, in_play=True))

        ready = ReadyCards.of(cards)

    assert ready.phrase_ids == frozenset({phrase_id_of(ready_id)})
