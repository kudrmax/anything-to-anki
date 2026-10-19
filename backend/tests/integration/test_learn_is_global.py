"""Q12: a Learn not exported yet is global. Once a word is marked Learn in one source, its
cards in another source are done, labelled "Learn in another source"; calibration and the
analysis of a new source skip the word. All of it read from the request's one snapshot."""
from __future__ import annotations

from collections.abc import Generator  # noqa: TC003
from typing import TYPE_CHECKING, Any
from unittest.mock import MagicMock

import pytest
from backend.application.dto.analysis_dtos import AnalyzeTextRequest
from backend.application.use_cases.get_bootstrap_words import GetBootstrapWordsUseCase
from backend.domain.entities.bootstrap_word_entry import BootstrapWordEntry
from backend.domain.value_objects.cefr_level import CEFRLevel
from backend.domain.value_objects.document import Document, Line, Paragraph, ParagraphMode
from backend.infrastructure.api.app import app
from backend.infrastructure.api.dependencies import get_db_session, get_session_factory
from backend.infrastructure.container import Container
from backend.infrastructure.persistence.database import Base, _enable_sqlite_foreign_keys
from fastapi.testclient import TestClient
from sqlalchemy import StaticPool, create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from tests.decision_support import Decisions
from tests.integration.conftest import insert_source
from tests.word_support import insert_word, phrase_id_of

if TYPE_CHECKING:
    from backend.domain.value_objects.vocabulary import Vocabulary

pytestmark = pytest.mark.integration

# JSON of the API, read as the web reads it.
Json = Any

HERE, THERE = 1, 2
WORD, WORD_THERE = 1, 2
LEMMA = "relentless"
NEW_SOURCE = Document((
    Paragraph(lines=(Line("The relentless rain kept falling on the town."),),
              mode=ParagraphMode.FLOW),
))


@pytest.fixture()
def factory() -> Generator[sessionmaker[Session], None, None]:
    engine = create_engine(
        "sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool,
    )
    event.listen(engine, "connect", _enable_sqlite_foreign_keys)
    Base.metadata.create_all(engine)
    with sessionmaker(bind=engine)() as session:
        insert_source(session, HERE)
        insert_source(session, THERE)
        insert_word(session, WORD, source_id=HERE, lemma=LEMMA)
        insert_word(session, WORD_THERE, source_id=THERE, lemma=LEMMA)
        session.commit()
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
        response = c.post(f"/phrases/{phrase_id_of(WORD)}/decision", json={"button": "learn"})
        assert response.status_code == 200
        yield c
    app.dependency_overrides.clear()


def _vocabulary(factory: sessionmaker[Session]) -> Vocabulary:
    with factory() as session:
        return Decisions(session).vocabulary.snapshot()


def test_the_cards_in_another_source_are_done_as_learn_elsewhere(client: TestClient) -> None:
    [card] = client.get(f"/sources/{THERE}/candidates").json()

    assert card["shown"] == {
        "status": "learn", "skipped": False, "where": "other_source", "tone": "learning",
    }
    assert card["state"]["note"] == "learn_elsewhere"
    assert card["is_done"]


def test_a_new_source_does_not_offer_the_word(
    client: TestClient, factory: sessionmaker[Session],
) -> None:
    del client
    analyse = Container().analyze_text_use_case().execute

    def offered(vocabulary: Vocabulary | None) -> set[str]:
        request = (
            AnalyzeTextRequest(user_level="B1") if vocabulary is None
            else AnalyzeTextRequest(user_level="B1", vocabulary=vocabulary)
        )
        return {word.lemma for word in analyse(NEW_SOURCE, request).words}

    assert LEMMA in offered(None), "the word is new to a user who has not marked it"
    assert LEMMA not in offered(_vocabulary(factory))


def test_calibration_skips_the_word(client: TestClient, factory: sessionmaker[Session]) -> None:
    del client
    index = MagicMock()
    index.get_all_entries.return_value = [
        BootstrapWordEntry(LEMMA, CEFRLevel.B2, 3.2),
        BootstrapWordEntry("drift", CEFRLevel.B2, 4.2),
    ]
    settings = MagicMock()
    settings.get.return_value = "B1"
    with factory() as session:
        vocabulary = Decisions(session).vocabulary
        offered = GetBootstrapWordsUseCase(index, vocabulary, settings).execute([])

    assert [word.lemma for word in offered] == ["drift"]
