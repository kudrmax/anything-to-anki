"""A card stands in Ready only when its phrase is Ready now and earned Ready when it was added
or its text last changed. What the user knows, learns or sets afterwards can take a card out
of Ready and bring it back, but never into Ready if the phrase did not earn it."""
from __future__ import annotations

from collections.abc import Generator  # noqa: TC003
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any

import pytest
from backend.infrastructure.api.app import app
from backend.infrastructure.api.dependencies import get_db_session, get_session_factory
from backend.infrastructure.persistence.database import (
    Base,
    _enable_sqlite_foreign_keys,
)
from backend.infrastructure.persistence.models import WordDecisionModel, dump_phrase
from backend.infrastructure.persistence.sqla_known_word_repository import (
    SqlaKnownWordRepository,
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

SOURCE, OTHER_SOURCE = 1, 2
EMBER, ZEPHYR, DRIFT, SPARK = 1, 2, 3, 4
EMBER_PHRASE = phrase_id_of(EMBER)
DRIFT_PHRASE = phrase_id_of(DRIFT)
SPARK_PHRASE = phrase_id_of(SPARK)
QUILL_INDEX = 2
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
        insert_word(session, DRIFT, lemma="drift", zipf_frequency=EMBER_ZIPF)
        _store_phrase(session, DRIFT_PHRASE, phrase("a drift quill", "drift"), "ready")
        insert_source(session, OTHER_SOURCE)
        insert_word(session, SPARK, source_id=OTHER_SOURCE, lemma="spark")
        _store_phrase(session, SPARK_PHRASE, phrase("a spark quill", "spark"), "ready")
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


def _section(client: TestClient, source_id: int, phrase_id: int) -> str:
    source = client.get("/review", params={"scope": f"source-{source_id}"}).json()
    card = next(c for c in source["candidates"] if c["phrase_id"] == phrase_id)
    return str(card["section"])


def _ember(client: TestClient) -> str:
    return _section(client, SOURCE, EMBER_PHRASE)


def _drift(client: TestClient) -> str:
    return _section(client, SOURCE, DRIFT_PHRASE)


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
    SqlaSettingsRepository(session).set("frequent_word_threshold", "off")


def _cefr_level_setting(session: Session) -> None:
    SqlaSettingsRepository(session).set("cefr_level", "C2")


def _commit(factory: sessionmaker[Session], change: Callable[[Session], None]) -> None:
    with factory() as session:
        change(session)
        session.commit()


def test_an_extra_card_stays_extra_when_the_other_word_becomes_known(
    client: TestClient, factory: sessionmaker[Session],
) -> None:
    assert _ember(client) == "extra"

    _commit(factory, _known_zephyr)

    assert _ember(client) == "extra"


def test_an_extra_card_stays_extra_when_the_learning_timer_comes_due(
    client: TestClient, factory: sessionmaker[Session],
) -> None:
    _commit(factory, _learning_timer_expired)

    assert _ember(client) == "extra"


@pytest.mark.parametrize("change", [
    _calibration, _threshold_setting, _cefr_level_setting,
], ids=lambda f: f.__name__.lstrip("_"))
def test_settings_alone_do_not_put_an_extra_card_into_ready(
    client: TestClient, factory: sessionmaker[Session], change: Callable[[Session], None],
) -> None:
    _commit(factory, _known_zephyr)
    _commit(factory, change)

    assert _ember(client) != "ready"


def test_a_threshold_change_takes_a_ready_card_out_of_ready(
    client: TestClient, factory: sessionmaker[Session],
) -> None:
    assert _drift(client) == "ready"

    _commit(factory, lambda s: SqlaSettingsRepository(s).set("frequent_word_threshold", "4.0"))

    assert _drift(client) == "probably_known"


def test_an_unknown_word_report_takes_the_ready_cards_with_that_word_out_of_ready(
    client: TestClient,
) -> None:
    assert _drift(client) == "ready"
    assert _section(client, OTHER_SOURCE, SPARK_PHRASE) == "ready"

    reported = client.post(
        f"/phrases/{DRIFT_PHRASE}/report", json={"unknown_words": [QUILL_INDEX]},
    )
    assert reported.status_code == 201

    assert _drift(client) == "extra"
    assert _section(client, OTHER_SOURCE, SPARK_PHRASE) == "extra"


def test_removing_the_unknown_word_returns_the_cards_to_ready(client: TestClient) -> None:
    client.post(f"/phrases/{DRIFT_PHRASE}/report", json={"unknown_words": [QUILL_INDEX]})
    [word] = client.get("/unknown-words").json()

    assert client.delete(f"/unknown-words/{word['id']}").status_code == 200

    assert _drift(client) == "ready"
    assert _section(client, OTHER_SOURCE, SPARK_PHRASE) == "ready"


def test_removing_known_returns_a_done_card_to_ready_when_it_earned_ready(
    client: TestClient,
) -> None:
    decided = client.post(f"/phrases/{DRIFT_PHRASE}/decision", json={"button": "known"})
    assert decided.status_code == 200
    assert _drift(client) == "reviewed"

    [entry] = [w for w in client.get("/known-words").json() if w["lemma"] == "drift"]
    assert client.delete(f"/known-words/{entry['removal_key']}").status_code == 200

    assert _drift(client) == "ready"


def test_removing_known_returns_a_done_card_to_extra_when_it_earned_extra(
    client: TestClient,
) -> None:
    decided = client.post(f"/phrases/{EMBER_PHRASE}/decision", json={"button": "known"})
    assert decided.status_code == 200
    assert _ember(client) == "reviewed"

    [entry] = [w for w in client.get("/known-words").json() if w["lemma"] == "ember"]
    assert client.delete(f"/known-words/{entry['removal_key']}").status_code == 200

    assert _ember(client) == "extra"


def test_ready_generation_takes_the_cards_that_are_ready_now_and_earned_ready(
    client: TestClient, factory: sessionmaker[Session],
) -> None:
    def missing(kind: str) -> int:
        kinds = client.get(
            "/review/generation", params={"scope": f"source-{SOURCE}"},
        ).json()["kinds"]
        return int(next(k for k in kinds if k["kind"] == kind)["ready_missing"])

    assert missing("meaning") == 1, "drift is Ready; ember earned Extra"

    _commit(factory, _known_zephyr)
    assert missing("meaning") == 1, "ember is Ready now but did not earn it"

    client.post(f"/phrases/{DRIFT_PHRASE}/report", json={"unknown_words": [QUILL_INDEX]})
    assert missing("meaning") == 0, "drift left Ready"
