"""One `now` for every reader: 30 days after its export a word is Known on its card, in
other sources, in the sections of other phrases, in the Known list and in the stats, at the
same moment and with nothing written. A word in Unknown is never Known by its timer."""
from __future__ import annotations

from collections.abc import Generator  # noqa: TC003
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any

import pytest
from backend.application.utils.knowledge_scope import KnowledgeScope
from backend.domain.value_objects.learning_timer import LEARNING_KNOWN_AFTER
from backend.domain.value_objects.source_operation_kind import SourceOperationKind
from backend.infrastructure.api.app import app
from backend.infrastructure.api.dependencies import get_db_session, get_session_factory
from backend.infrastructure.container import KNOWLEDGE_SCOPE_KEY
from backend.infrastructure.persistence.database import Base, _enable_sqlite_foreign_keys
from backend.infrastructure.persistence.sqla_known_word_repository import (
    SqlaKnownWordRepository,
)
from backend.infrastructure.persistence.sqla_learning_query import SqlaLearningQuery
from backend.infrastructure.persistence.sqla_occurrence_repository import (
    SqlaOccurrenceRepository,
)
from backend.infrastructure.persistence.sqla_source_operation_lock import (
    SqlaSourceOperationLock,
)
from backend.infrastructure.persistence.sqla_unknown_word_repository import (
    SqlaUnknownWordRepository,
)
from fastapi.testclient import TestClient
from sqlalchemy import StaticPool, create_engine, event, text
from sqlalchemy.orm import Session, sessionmaker

from tests.decision_support import FixedClock
from tests.integration.conftest import insert_source
from tests.phrase_support import phrase
from tests.word_support import bind, insert_word, phrase_id_of

if TYPE_CHECKING:
    from backend.domain.ports.clock import Clock

pytestmark = pytest.mark.integration

# JSON of the API, read as the web reads it.
Json = Any

HERE, THERE, BOARD = 1, 2, 3
GLARE, SPARK = 1, 2                 # Learn in HERE, exported at EXPORTED
GLARE_THERE, SPARK_THERE, DRIFT = 3, 4, 5
ECHO, BLIND = 6, 7                  # in BOARD: ECHO skipped, BLIND's phrase shows glare
EXPORTED = datetime(2026, 9, 1, 12, tzinfo=UTC)
DAY_30 = EXPORTED + LEARNING_KNOWN_AFTER
DAY_29 = DAY_30 - timedelta(seconds=1)


class Moment:
    """The moment every request of the test runs at."""

    def __init__(self) -> None:
        self.at = DAY_30


@pytest.fixture()
def moment() -> Moment:
    return Moment()


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
    yield sessionmaker(bind=engine)
    engine.dispose()


def _scope(session: Session, clock: Clock) -> KnowledgeScope:
    return KnowledgeScope(
        clock=clock,
        known_word_repo=SqlaKnownWordRepository(session),
        unknown_word_repo=SqlaUnknownWordRepository(session),
        learning_query=SqlaLearningQuery(session),
    )


@pytest.fixture()
def client(factory: sessionmaker[Session], moment: Moment) -> Generator[TestClient, None, None]:
    def override_session() -> Generator[Session, None, None]:
        with factory() as session:
            # The request's scope, as the container makes it, on the test's clock.
            session.info[KNOWLEDGE_SCOPE_KEY] = _scope(session, FixedClock(moment.at))
            yield session

    app.dependency_overrides[get_db_session] = override_session
    app.dependency_overrides[get_session_factory] = lambda: factory
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def _seed(session: Session) -> None:
    since = EXPORTED.replace(tzinfo=None).isoformat(sep=" ")
    insert_source(session, HERE)
    insert_source(session, THERE)
    for word_id, lemma in ((GLARE, "glare"), (SPARK, "spark")):
        insert_word(session, word_id, source_id=HERE, lemma=lemma, status="learn")
        bind(session, word_id, phrase_id_of(word_id), since=since)
    SqlaUnknownWordRepository(session).add("spark")
    insert_word(session, GLARE_THERE, source_id=THERE, lemma="glare")
    insert_word(session, SPARK_THERE, source_id=THERE, lemma="spark")
    insert_word(session, DRIFT, source_id=THERE, lemma="drift")
    # Only the target is new once glare is known: Ready; while glare is learning: Extra.
    SqlaOccurrenceRepository(session).write_text(
        phrase_id_of(DRIFT),
        phrase("The glare drifts.", "drift", new=("glare", "drifts"),
               lemmas={"drifts": "drift"}),
        None,
    )
    insert_source(session, BOARD)
    insert_word(session, ECHO, source_id=BOARD, lemma="echo", status="skip")
    insert_word(session, BLIND, source_id=BOARD, lemma="blind")
    occurrences = SqlaOccurrenceRepository(session)
    occurrences.write_text(
        phrase_id_of(ECHO), phrase("The echo fades.", "echo", new=("echo",)), None,
    )
    occurrences.write_text(
        phrase_id_of(BLIND),
        phrase("The glare blinds.", "blind", new=("glare", "blinds"),
               lemmas={"blinds": "blind"}),
        None,
    )


def _card(client: TestClient, source_id: int, word_id: int) -> Json:
    cards = client.get(f"/sources/{source_id}/candidates").json()
    return next(card for card in cards if card["word_id"] == word_id)


def _known_list(client: TestClient) -> list[Json]:
    return list(client.get("/known-words").json())


def _known_count(client: TestClient) -> int:
    return int(client.get("/stats").json()["known_word_count"])


def test_at_day_30_every_reader_sees_the_word_known(client: TestClient) -> None:
    own = _card(client, HERE, GLARE)
    assert own["shown"]["status"] == "known"
    assert own["state"]["note"] == "known_by_timer"
    there = _card(client, THERE, GLARE_THERE)
    assert there["shown"] == {
        "status": "known", "skipped": False, "where": "other_source", "tone": "settled",
    }
    assert there["state"]["note"] == "known_elsewhere"
    assert there["is_done"]
    assert _card(client, THERE, DRIFT)["section"] == "ready"
    assert [(w["lemma"], w["by_timer"]) for w in _known_list(client)] == [("glare", True)]
    assert _known_count(client) == 1
    learning = client.get("/vocabulary/learning").json()
    assert learning["in_anki"] == []


def test_at_day_29_every_reader_sees_the_word_learning(
    client: TestClient, moment: Moment,
) -> None:
    moment.at = DAY_29

    own = _card(client, HERE, GLARE)
    assert own["shown"]["status"] == "learning"
    assert own["state"]["note"] == "in_anki"
    assert own["state"]["known_on"].startswith(DAY_30.date().isoformat())
    assert _card(client, THERE, GLARE_THERE)["shown"] == {
        "status": "learning", "skipped": False, "where": "other_source", "tone": "learning",
    }
    assert _card(client, THERE, DRIFT)["section"] == "extra"
    assert _known_list(client) == []
    assert _known_count(client) == 0
    learning = client.get("/vocabulary/learning").json()
    assert [(w["lemma"], w["known_on"][:10]) for w in learning["in_anki"]] == [
        ("glare", DAY_30.date().isoformat()),
    ]


def test_a_word_in_unknown_is_never_known_by_its_timer(client: TestClient) -> None:
    own = _card(client, HERE, SPARK)
    assert own["shown"]["status"] == "learning"
    assert own["state"]["note"] == "in_anki"
    assert own["state"]["known_on"] is None
    assert _card(client, THERE, SPARK_THERE)["shown"]["where"] == "nowhere"
    assert "spark" not in {w["lemma"] for w in _known_list(client)}
    assert _known_count(client) == 1


@pytest.mark.parametrize("lemma", ["glare", "Glare"])
def test_deleting_a_word_known_by_its_timer_makes_its_cards_new_everywhere(
    client: TestClient, factory: sessionmaker[Session], lemma: str,
) -> None:
    response = client.delete(f"/known-words/by-lemma/{lemma}")

    assert response.status_code == 200
    own = _card(client, HERE, GLARE)
    assert own["shown"]["status"] == "new"
    assert own["state"]["note"] is None
    there = _card(client, THERE, GLARE_THERE)
    assert there["shown"]["where"] == "nowhere"
    assert not there["is_done"]
    assert _known_list(client) == []
    assert _known_count(client) == 0
    with factory() as session:
        released = session.execute(text(
            "SELECT released_at IS NOT NULL FROM anki_synced_cards WHERE phrase_id = :id"
        ), {"id": phrase_id_of(GLARE)}).scalar_one()
    assert released


def test_deleting_a_word_known_by_its_timer_waits_for_a_busy_source(
    client: TestClient, factory: sessionmaker[Session],
) -> None:
    with factory() as session:
        SqlaSourceOperationLock(session).acquire(THERE, SourceOperationKind.REBUILD)
        session.commit()

    response = client.delete("/known-words/by-lemma/glare")

    assert response.status_code == 409
    assert [w["lemma"] for w in _known_list(client)] == ["glare"]
    assert _card(client, HERE, GLARE)["shown"]["status"] == "known"


def test_a_lemma_with_a_slash_reaches_the_delete(client: TestClient) -> None:
    response = client.delete("/known-words/by-lemma/and/or")

    assert (response.status_code, response.json()) == (200, {"deleted": "and/or"})


def _listed(client: TestClient, source_id: int) -> Json:
    return next(s for s in client.get("/sources").json() if s["id"] == source_id)


def _stored_status(factory: sessionmaker[Session], source_id: int) -> str:
    with factory() as session:
        return str(session.execute(
            text("SELECT status FROM sources WHERE id = :id"), {"id": source_id},
        ).scalar_one())


def test_a_timer_coming_due_reopens_a_reviewed_source_with_nothing_written(
    client: TestClient, factory: sessionmaker[Session], moment: Moment,
) -> None:
    """Day 29: glare is learning, so BLIND's phrase is Extra and the skipped ECHO is the
    only Ready card: reviewed. Day 30: glare is known, BLIND's phrase is Ready and open."""
    moment.at = DAY_29
    before = _listed(client, BOARD)
    reviewed_before = client.get("/collections").json()["all"]["reviewed"]

    moment.at = DAY_30
    after = _listed(client, BOARD)

    assert (before["status"], before["stage"], before["review_fraction"]) == (
        "reviewed", "reviewed", 1.0,
    )
    assert (after["status"], after["stage"], after["review_fraction"]) == (
        "partially_reviewed", "in_progress", 0.5,
    )
    assert client.get("/collections").json()["all"]["reviewed"] == reviewed_before - 1
    assert after["can_review"]
    assert not after["can_export"], "nothing in BOARD is to learn"
    assert _stored_status(factory, BOARD) == "done"
