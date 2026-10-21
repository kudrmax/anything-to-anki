"""Removing a word from Known in Settings (design §2.7, PRINCIPLE, Q5) and adding it there
after a Learn that was not exported (Q15: the later user action wins)."""
from __future__ import annotations

from collections.abc import Generator  # noqa: TC003
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from backend.domain.value_objects.source_operation_kind import SourceOperationKind
from backend.infrastructure.api.app import app
from backend.infrastructure.api.dependencies import get_db_session, get_session_factory
from backend.infrastructure.persistence.database import Base, _enable_sqlite_foreign_keys
from backend.infrastructure.persistence.sqla_source_operation_lock import (
    SqlaSourceOperationLock,
)
from fastapi.testclient import TestClient
from sqlalchemy import StaticPool, create_engine, event, text
from sqlalchemy.orm import Session, sessionmaker

from tests.integration.conftest import insert_source
from tests.projection_support import rebuild_projection
from tests.review_window_support import review_list
from tests.word_marks_support import insert_known
from tests.word_support import bind, insert_word, phrase_id_of

pytestmark = pytest.mark.integration

Json = Any

HERE, THERE, ELSEWHERE = 1, 2, 3
CHOSEN, BOUND, OPEN_LEARN, SKIPPED, DECIDED_KNOWN = 1, 2, 3, 4, 5   # in HERE; BOUND in ELSEWHERE
BOUND_THERE = 6                                                       # in THERE
ENTRY_ID = 1


@pytest.fixture()
def factory() -> Generator[sessionmaker[Session], None, None]:
    engine = create_engine(
        "sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool,
    )
    event.listen(engine, "connect", _enable_sqlite_foreign_keys)
    Base.metadata.create_all(engine)
    with sessionmaker(bind=engine)() as session:
        _seed(session)
        session.commit()
        rebuild_projection(session)
    yield sessionmaker(bind=engine)
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


def _seed(session: Session) -> None:
    since = (datetime.now(UTC) - timedelta(days=1)).replace(tzinfo=None).isoformat(sep=" ")
    insert_source(session, HERE)
    insert_source(session, THERE)
    insert_source(session, ELSEWHERE)
    insert_known(session, "glare", "NOUN")
    insert_known(session, "spark", "NOUN", "VERB")
    session.flush()
    insert_word(session, CHOSEN, source_id=HERE, lemma="glare", status="known")
    insert_word(session, BOUND, source_id=ELSEWHERE, lemma="glare", status="learn")
    bind(session, BOUND, phrase_id_of(BOUND), note_id=901, since=since)
    insert_word(session, BOUND_THERE, source_id=THERE, lemma="glare", status="learn")
    bind(session, BOUND_THERE, phrase_id_of(BOUND_THERE), note_id=902, since=since)
    insert_word(session, DECIDED_KNOWN, source_id=HERE, lemma="spark", status="known")
    insert_word(session, OPEN_LEARN, source_id=HERE, lemma="drift", status="learn")
    insert_word(session, SKIPPED, source_id=HERE, lemma="echo", status="skip")


def _card(client: TestClient, source_id: int, word_id: int) -> Json:
    cards = review_list(client, f"source-{source_id}")
    return next(card for card in cards if card["word_id"] == word_id)


def _removal_key(client: TestClient, lemma: str, pos: str) -> str:
    return str(next(
        w["removal_key"] for w in client.get("/known-words").json()
        if (w["lemma"], w["pos"]) == (lemma, pos)
    ))


def _released(factory: sessionmaker[Session], word_id: int) -> bool:
    with factory() as session:
        return bool(session.execute(text(
            "SELECT released_at IS NOT NULL FROM anki_synced_cards WHERE phrase_id = :id"
        ), {"id": phrase_id_of(word_id)}).scalar_one())


def test_removing_the_last_entry_makes_every_card_of_the_word_new_and_releases_it(
    client: TestClient, factory: sessionmaker[Session],
) -> None:
    assert _card(client, HERE, CHOSEN)["shown"]["status"] == "known"
    assert _card(client, ELSEWHERE, BOUND)["shown"]["status"] == "known"

    key = _removal_key(client, "glare", "NOUN")
    assert client.delete(f"/known-words/{key}").status_code == 200

    assert _card(client, HERE, CHOSEN)["shown"]["status"] == "new"
    assert _card(client, ELSEWHERE, BOUND)["shown"]["status"] == "new"
    assert _card(client, THERE, BOUND_THERE)["shown"]["status"] == "new"
    assert _released(factory, BOUND)
    assert _released(factory, BOUND_THERE)
    assert "glare" not in {w["lemma"] for w in client.get("/known-words").json()}


def test_removing_one_of_two_entries_of_a_word_changes_nothing_else(
    client: TestClient, factory: sessionmaker[Session],
) -> None:
    before = _card(client, HERE, DECIDED_KNOWN)["shown"]["status"]

    client.delete(f"/known-words/{_removal_key(client, 'spark', 'VERB')}")

    assert before == "known"
    assert _card(client, HERE, DECIDED_KNOWN)["shown"]["status"] == "known"
    assert [(w["lemma"], w["pos"]) for w in client.get("/known-words").json()
            if w["lemma"] == "spark"] == [("spark", "NOUN")]


def test_removing_the_last_entry_waits_for_a_busy_source(
    client: TestClient, factory: sessionmaker[Session],
) -> None:
    with factory() as session:
        SqlaSourceOperationLock(session).acquire(THERE, SourceOperationKind.UPDATE)
        session.commit()

    response = client.delete(f"/known-words/{_removal_key(client, 'glare', 'NOUN')}")

    assert response.status_code == 409
    assert _card(client, HERE, CHOSEN)["shown"]["status"] == "known"
    assert "glare" in {w["lemma"] for w in client.get("/known-words").json()}


def test_adding_a_word_to_known_after_an_unexported_learn_makes_the_card_known(
    client: TestClient,
) -> None:
    with_open = _card(client, HERE, OPEN_LEARN)
    assert with_open["shown"]["status"] == "learn"

    client.post("/api/bootstrap/known", json={"lemmas": ["drift", "echo"]})

    assert _card(client, HERE, OPEN_LEARN)["shown"]["status"] == "known"
    assert _card(client, HERE, SKIPPED)["shown"]["skipped"]
    assert _card(client, HERE, DECIDED_KNOWN)["shown"]["status"] == "known"
