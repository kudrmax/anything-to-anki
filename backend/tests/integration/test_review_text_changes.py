"""The marks of the chunks of text an open review served, kept up to date by its answers
(Stage 7): a change that moves, adds or takes away a mark in a served chunk sends that
chunk's marks as a fresh read gives them; a press that only decides cards sends none and
reads no document; a review opened again takes the chunks its client holds."""
from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

import pytest
from backend.application.dto.review_dtos import ReviewContext
from backend.application.utils.source_texts import SourceTexts
from backend.domain.services import text_chunks
from backend.domain.services.text_chunks import LAST_BLOCK
from backend.domain.value_objects.document_position import DocumentPosition
from backend.infrastructure.api.app import app
from backend.infrastructure.api.dependencies import (
    get_container,
    get_db_session,
    get_session_factory,
)
from backend.infrastructure.persistence.database import Base, _enable_sqlite_foreign_keys
from backend.infrastructure.persistence.models import CollectionModel, SourceModel
from backend.infrastructure.persistence.sqla_document_repository import SqlaDocumentRepository
from fastapi.testclient import TestClient
from sqlalchemy import StaticPool, create_engine, event, text
from sqlalchemy.orm import Session, sessionmaker

from tests.integration import test_card_state_projection_differential as corpus
from tests.integration.test_review_mutation import NEW_LINE, World
from tests.integration.test_review_text import (
    CHUNK_CHARS,
    COLLECTION,
    EPISODE,
    EPISODE_DOCUMENT,
    GIVE,
    GIVE_UP,
    GLARE,
    HOPE_TEXT,
    NOTES,
    PILOT,
    PILOT_CARDS,
    PILOT_DOCUMENT,
    SCOPE,
    _seed,
    _selection,
    _whole,
)
from tests.projection_support import rebuild_projection
from tests.review_window_support import open_review, review_text
from tests.word_support import store_cards

if TYPE_CHECKING:
    from collections.abc import Iterator

    from backend.application.dto.document_dtos import TextChunkDTO
    from backend.domain.value_objects.document import Document

pytestmark = pytest.mark.integration

HARBOUR_TEXT = "A quiet harbour at dawn."
# The word `quiet` in the last chunk of the pilot and in the episode.
QUIET_PILOT, QUIET_EPISODE, HARBOUR = len(PILOT_CARDS), len(PILOT_CARDS) + 1, len(PILOT_CARDS) + 2
CARDS = [
    *PILOT_CARDS,
    _seed(PILOT, "quiet", HOPE_TEXT, "quiet", _whole(5), pos="ADJ"),
    _seed(EPISODE, "quiet", HARBOUR_TEXT, "quiet", DocumentPosition(0, 0, 0, 0, 24), pos="ADJ"),
    _seed(EPISODE, "harbour", HARBOUR_TEXT, "harbour", DocumentPosition(0, 0, 0, 0, 24)),
]
FIRST, SECOND, LAST = 0, 2, 4
OUTSIDE_THE_SET = 99
# Lines of source 1 the Rebuild brings, each with words no other line of it has.
THIRD_LINE = "Pelicans squabble over the glistening mackerel at noon."
LAST_LINE = "Barnacles encrust the corroded anchor beneath the jetty."


@pytest.fixture()
def factory() -> Iterator[sessionmaker[Session]]:
    engine = create_engine(
        "sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool,
    )
    event.listen(engine, "connect", _enable_sqlite_foreign_keys)
    Base.metadata.create_all(engine)
    made = sessionmaker(bind=engine)
    yield made
    engine.dispose()


@pytest.fixture()
def ids(factory: sessionmaker[Session]) -> list[int]:
    """The cards by their index in CARDS; the pilot's in three chunks, as in
    test_review_text."""
    with factory() as session:
        session.add(CollectionModel(id=COLLECTION, name="Show"))
        session.add_all([
            SourceModel(
                id=source_id, title=title, status="done", collection_id=COLLECTION,
                created_at=datetime(2026, 1, day, tzinfo=UTC),
            )
            for day, (source_id, title) in enumerate(
                [(PILOT, "Pilot"), (EPISODE, "Episode 2"), (NOTES, "Notes")], start=1,
            )
        ])
        session.flush()
        documents = SqlaDocumentRepository(session)
        documents.save(PILOT, PILOT_DOCUMENT)
        documents.save(EPISODE, EPISODE_DOCUMENT)
        seeded = store_cards(session, CARDS)
        session.execute(text(
            "UPDATE phrases SET block = json_extract(phrase_position, '$[0]')"
            " WHERE json_extract(phrase_position, '$[0]') != 5"
        ))
        session.commit()
        rebuild_projection(session)
    return [card.phrase_id for card in seeded]


@pytest.fixture()
def client(
    factory: sessionmaker[Session], ids: list[int], monkeypatch: pytest.MonkeyPatch,
) -> Iterator[TestClient]:
    def override_session() -> Iterator[Session]:
        with factory() as session:
            yield session

    monkeypatch.setattr(text_chunks, "TEXT_CHUNK_CHARS", CHUNK_CHARS)
    monkeypatch.setattr(get_container(), "_source_texts", SourceTexts())
    app.dependency_overrides[get_db_session] = override_session
    app.dependency_overrides[get_session_factory] = lambda: factory
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


# Any: the raw JSON of the API, as the test reads it.
def _on(review: dict[str, Any], current: int | None = None) -> dict[str, Any]:
    params = {
        "review_id": review["review_id"], "since": review["revision"],
        "current": current or review["focus_id"],
    }
    return {k: v for k, v in params.items() if v is not None}


# Any: the raw JSON of the API, as the test reads it.
def _fresh(
    client: TestClient, review: dict[str, Any], source_id: int, block: int,
) -> dict[str, Any]:
    """The chunk's marks as a fresh read gives them, in the form of an answer's
    `highlights`."""
    chunk = review_text(client, review, source_id, block)["text"]
    return {
        "source_id": source_id, "first_block": chunk["first_block"],
        "highlights": chunk["highlights"],
    }


# Any: the raw JSON of the API, as the test reads it.
def _marked(chunk: dict[str, Any]) -> list[int]:
    return [mark["phrase_id"] for mark in chunk["highlights"]]


# Any: the raw JSON of the API, as the test reads it.
def _ok(response: Any) -> dict[str, Any]:  # noqa: ANN401 — the test client's response
    assert response.status_code in (200, 201), response.text
    answer: dict[str, Any] = response.json()
    return answer


def test_a_boundary_edit_sends_its_chunk_as_a_fresh_read_gives_it(
    client: TestClient, ids: list[int],
) -> None:
    review = open_review(client, SCOPE)
    review_text(client, review, PILOT, SECOND)
    review_text(client, review, PILOT, LAST_BLOCK)

    answer = _ok(client.put(
        f"/phrases/{ids[GLARE]}/phrase-boundary",
        json={"selection": _selection((3, 0, 5), (3, 0, 21))}, params=_on(review),
    ))

    assert str(ids[GLARE]) in answer["done"], "the edit moved the card's revision"
    assert answer["highlights"] == [_fresh(client, review, PILOT, SECOND)]


def test_an_added_word_sends_its_chunk_with_the_new_mark(client: TestClient) -> None:
    review = open_review(client, SCOPE)
    review_text(client, review, PILOT, SECOND)

    answer = _ok(client.post(
        f"/sources/{PILOT}/candidates/manual",
        json={"target_words": [1], "selection": _selection((2, 0, 6), (2, 0, 25))},
        params=_on(review),
    ))

    [chunk] = answer["highlights"]
    assert answer["focus_id"] in _marked(chunk)
    assert chunk == _fresh(client, review, PILOT, SECOND)


def test_an_example_takes_its_cards_mark_away_and_shows_the_mark_it_covered(
    client: TestClient, ids: list[int],
) -> None:
    review = open_review(client, SCOPE)
    before = review_text(client, review, PILOT, FIRST)["text"]
    assert ids[GIVE_UP] in _marked(before)
    assert ids[GIVE] not in _marked(before)

    answer = _ok(client.post(
        f"/phrases/{ids[GIVE_UP]}/replace-with-example",
        json={"example_text": "They never **gave up** on the old harbour."},
        params=_on(review, ids[GIVE_UP]),
    ))

    [chunk] = answer["highlights"]
    assert ids[GIVE_UP] not in _marked(chunk)
    assert ids[GIVE] in _marked(chunk)
    assert chunk == _fresh(client, review, PILOT, FIRST)


def test_learn_on_a_lemma_in_two_served_chunks_sends_no_marks_and_reads_no_document(
    client: TestClient, ids: list[int], monkeypatch: pytest.MonkeyPatch,
) -> None:
    review = open_review(client, SCOPE)
    assert ids[QUIET_PILOT] in _marked(review_text(client, review, PILOT, LAST_BLOCK)["text"])
    assert ids[QUIET_EPISODE] in _marked(review_text(client, review, EPISODE, 0)["text"])
    reads: list[int] = []
    read = SqlaDocumentRepository.get

    def counted(repo: SqlaDocumentRepository, source_id: int) -> Document | None:
        reads.append(source_id)
        return read(repo, source_id)

    monkeypatch.setattr(SqlaDocumentRepository, "get", counted)

    answer = _ok(client.post(
        f"/phrases/{ids[QUIET_PILOT]}/decision", json={"button": "learn"},
        params=_on(review, ids[QUIET_PILOT]),
    ))

    assert answer["highlights"] == []
    assert answer["done"][str(ids[QUIET_PILOT])] is True
    assert answer["done"][str(ids[QUIET_EPISODE])] is True
    assert reads == []


def test_a_review_opened_again_sends_the_marks_of_the_chunks_its_client_holds(
    client: TestClient, ids: list[int],
) -> None:
    review = open_review(client, SCOPE)
    held = [
        {"source_id": PILOT, "first_block": LAST},
        {"source_id": OUTSIDE_THE_SET, "first_block": 0},
        {"source_id": PILOT, "first_block": 1},
        {"source_id": PILOT, "first_block": FIRST},
        {"source_id": NOTES, "first_block": 0},
    ]

    again = _ok(client.post("/api/review", json={"scope": SCOPE, "text_chunks": held}))

    assert again["highlights"] == [
        _fresh(client, review, PILOT, LAST), _fresh(client, review, PILOT, FIRST),
    ]
    edited = _ok(client.put(
        f"/phrases/{ids[GIVE_UP]}/phrase-boundary",
        json={"selection": _selection((1, 0, 3), (1, 1, 13))}, params=_on(again),
    ))
    assert [(c["source_id"], c["first_block"]) for c in edited["highlights"]] == [
        (PILOT, FIRST),
    ]


def test_a_source_that_left_the_set_gets_no_marks(
    client: TestClient, ids: list[int], factory: sessionmaker[Session],
) -> None:
    review = open_review(client, SCOPE)
    review_text(client, review, EPISODE, 0)
    with factory() as session:
        session.execute(text("UPDATE sources SET collection_id = NULL WHERE id = :id"), {
            "id": EPISODE,
        })
        session.commit()
    left = _ok(client.get(f"/api/review/{review['review_id']}/changes", params=_on(review)))
    assert left["highlights"] == []
    assert left["contents_version"] == 1

    answer = _ok(client.put(
        f"/phrases/{ids[HARBOUR]}/phrase-boundary",
        json={"selection": _selection((0, 0, 2), (0, 0, 15))}, params=_on(left),
    ))

    assert answer["highlights"] == []


# --- a Rebuild, on the processed corpus ----------------------------------------------------

@pytest.fixture(scope="module")
def built() -> Iterator[corpus._Scenario]:  # noqa: SLF001
    with corpus.processed_corpus() as processed:
        yield processed


def test_a_rebuild_sends_the_served_chunks_it_changed_and_no_other(
    built: corpus._Scenario,  # noqa: SLF001
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Every line its own chunk; the first and the last are served. The Rebuild changes the
    first, the third and the last line: the third is not sent."""
    monkeypatch.setattr(text_chunks, "TEXT_CHUNK_CHARS", 1)
    monkeypatch.setattr(built.container, "_source_texts", SourceTexts())
    world = World(built)
    opened = world.open()
    ctx = ReviewContext(review_id=opened.review_id, since=opened.revision, current=None)
    for block in (0, LAST_BLOCK):
        with world.factory() as session:
            world.container.review_window_use_case(session).text(ctx, 1, block)
    lines = list(corpus.SOURCES[1])
    last = len(lines) - 1

    world.source_one(NEW_LINE, lines[1], THIRD_LINE, *lines[3:last], LAST_LINE)
    update = world.changes(ctx)

    assert [(c.source_id, c.first_block) for c in update.highlights] == [(1, 0), (1, last)]
    for chunk in update.highlights:
        assert chunk.highlights == _read(world, ctx, chunk.first_block).highlights
        assert chunk.highlights != []


def test_a_rebuild_that_drops_the_last_line_sends_its_chunk_with_no_marks(
    built: corpus._Scenario,  # noqa: SLF001
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The phrases of the last line are deleted: where they stood is not stored any more,
    so any served chunk of the source may have marked them."""
    monkeypatch.setattr(text_chunks, "TEXT_CHUNK_CHARS", 1)
    monkeypatch.setattr(built.container, "_source_texts", SourceTexts())
    world = World(built)
    opened = world.open()
    ctx = ReviewContext(review_id=opened.review_id, since=opened.revision, current=None)
    for block in (0, LAST_BLOCK):
        with world.factory() as session:
            world.container.review_window_use_case(session).text(ctx, 1, block)
    lines = list(corpus.SOURCES[1])
    last = len(lines) - 1

    world.source_one(*lines[:last])
    update = world.changes(ctx)

    assert [(c.source_id, c.first_block, c.highlights) for c in update.highlights] == [
        (1, last, []),
    ]


def _read(world: World, ctx: ReviewContext, block: int) -> TextChunkDTO:
    with world.factory() as session:
        answer = world.container.review_window_use_case(session).text(ctx, 1, block)
    assert answer.text is not None
    return answer.text
