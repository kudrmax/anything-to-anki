"""The text of an open review in chunks of whole blocks: the contents of its set, each chunk
with its marks, and phrases selected on a chunk (Review Focus, Stage 7)."""
from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

import pytest
from backend.application.utils.source_texts import SourceTexts
from backend.domain.entities.stored_candidate import StoredCandidate
from backend.domain.services import text_chunks
from backend.domain.services.document_layout import ONE_BLOCK_MESSAGE
from backend.domain.services.text_chunks import LAST_BLOCK
from backend.domain.value_objects.document import (
    BLOCK_SEPARATOR,
    Document,
    Heading,
    Line,
    ListItem,
    Paragraph,
    ParagraphMode,
    block_text,
)
from backend.domain.value_objects.document_position import DocumentPosition
from backend.domain.value_objects.word_status import WordStatus
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

from tests.phrase_support import phrase
from tests.projection_support import rebuild_projection
from tests.review_window_support import open_review, review_contents, review_text
from tests.word_support import CardSeed, store_cards

if TYPE_CHECKING:
    from collections.abc import Iterator

pytestmark = pytest.mark.integration

COLLECTION = 7
PILOT, EPISODE, NOTES, LATER = 1, 2, 3, 4
SCOPE = str(COLLECTION)
# Three chunks of the pilot: blocks 0-1, 2-3 and 4-5.
CHUNK_CHARS = 60
FIRST_CHUNK, SECOND_CHUNK, LAST_CHUNK = (0, 2), (2, 4), (4, 6)

PILOT_DOCUMENT = Document((
    Heading(1, "Chapter one"),
    Paragraph(
        (Line("He gave up the relentless pursuit"), Line("of happiness.")), ParagraphMode.FLOW,
    ),
    ListItem((Line("First we lingered a while."),), ordered=True, depth=0),
    ListItem((Line("Then she glared back."),), ordered=True, depth=1),
    ListItem((Line("Then they left."),), ordered=True, depth=0),
    Paragraph((Line("She gave up her quiet hope."),), ParagraphMode.FLOW),
))
EPISODE_DOCUMENT = Document((
    Paragraph((Line("A quiet harbour at dawn."),), ParagraphMode.FLOW),
))
LATER_DOCUMENT = Document((Heading(1, "Later"),))


def _whole(block: int) -> DocumentPosition:
    """The place of a whole one-line block."""
    return DocumentPosition(block, 0, 0, 0, len(block_text(PILOT_DOCUMENT.blocks[block])))


def _seed(
    source_id: int, lemma: str, text_of: str, target: str, position: DocumentPosition,
    *, phrasal: bool = False, pos: str = "NOUN",
) -> CardSeed:
    return CardSeed(
        StoredCandidate(
            source_id=source_id, lemma=lemma, pos=pos, cefr_level="B2", zipf_frequency=3.0,
            occurrences=1, status=WordStatus.NEW, is_phrasal_verb=phrasal,
        ),
        phrase(text_of, target),
        position=position,
    )


PURSUIT_TEXT = block_text(PILOT_DOCUMENT.blocks[1])
HOPE_TEXT = block_text(PILOT_DOCUMENT.blocks[5])
PILOT_CARDS = [
    _seed(PILOT, "give up", PURSUIT_TEXT, "gave up", DocumentPosition(1, 0, 0, 1, 13),
          phrasal=True),
    _seed(PILOT, "give", PURSUIT_TEXT, "gave", DocumentPosition(1, 0, 0, 1, 13)),
    _seed(PILOT, "pursuit", PURSUIT_TEXT, "pursuit", DocumentPosition(1, 0, 0, 1, 13)),
    _seed(PILOT, "while", block_text(PILOT_DOCUMENT.blocks[2]), "while", _whole(2),
          pos="INTJ"),
    _seed(PILOT, "glare", block_text(PILOT_DOCUMENT.blocks[3]), "glared", _whole(3)),
    # Another phrase of each verb, in the last chunk: the phrasal verb over its verb again.
    _seed(PILOT, "give up", HOPE_TEXT, "gave up", _whole(5), phrasal=True),
    _seed(PILOT, "give", HOPE_TEXT, "gave", _whole(5)),
    _seed(PILOT, "hope", HOPE_TEXT, "hope", _whole(5)),
]
GIVE_UP, GIVE, PURSUIT, WHILE, GLARE, GIVE_UP_LATER, GIVE_LATER, HOPE = range(len(PILOT_CARDS))


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
def phrase_ids(factory: sessionmaker[Session]) -> list[int]:
    """The pilot's cards by their index in PILOT_CARDS. Every phrase but those of the last
    block has the key the analysis gives it; the others are picked by their place."""
    with factory() as session:
        session.add(CollectionModel(id=COLLECTION, name="Show"))
        session.add_all([
            SourceModel(
                id=PILOT, title="Pilot", status="done", collection_id=COLLECTION,
                created_at=datetime(2026, 1, 1, tzinfo=UTC),
            ),
            SourceModel(
                id=EPISODE, title="Episode 2", status="done", collection_id=COLLECTION,
                created_at=datetime(2026, 1, 2, tzinfo=UTC),
            ),
            SourceModel(
                id=NOTES, title="Notes", status="done", collection_id=COLLECTION,
                created_at=datetime(2026, 1, 3, tzinfo=UTC),
            ),
        ])
        session.flush()
        documents = SqlaDocumentRepository(session)
        documents.save(PILOT, PILOT_DOCUMENT)
        documents.save(EPISODE, EPISODE_DOCUMENT)
        seeded = store_cards(session, [
            *PILOT_CARDS,
            _seed(EPISODE, "harbour", "A quiet harbour at dawn.", "harbour",
                  DocumentPosition(0, 0, 0, 0, 24)),
        ])
        session.execute(text(
            "UPDATE phrases SET block = json_extract(phrase_position, '$[0]')"
            " WHERE json_extract(phrase_position, '$[0]') != 5"
        ))
        session.commit()
        rebuild_projection(session)
    return [card.phrase_id for card in seeded[:len(PILOT_CARDS)]]


@pytest.fixture()
def client(
    factory: sessionmaker[Session], phrase_ids: list[int], monkeypatch: pytest.MonkeyPatch,
) -> Iterator[TestClient]:
    """The app on the test's database, with short chunks and no text laid out before."""
    def override_session() -> Iterator[Session]:
        with factory() as session:
            yield session

    monkeypatch.setattr(text_chunks, "TEXT_CHUNK_CHARS", CHUNK_CHARS)
    container = get_container()
    monkeypatch.setattr(container, "_source_texts", SourceTexts())
    app.dependency_overrides[get_db_session] = override_session
    app.dependency_overrides[get_session_factory] = lambda: factory
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


# Any: the raw JSON of the API, as the test reads it.
def _documents(client: TestClient) -> dict[int, dict[str, Any]]:
    response = client.get("/api/review/documents", params={"scope": SCOPE})
    assert response.status_code == 200, response.text
    return {document["source_id"]: document for document in response.json()}


# Any: the raw JSON of the API, as the test reads it.
def _chunks(
    client: TestClient, review: dict[str, Any], source_id: int,
) -> list[dict[str, Any]]:
    """Every chunk of the source's text, one after another from the first block."""
    chunks: list[dict[str, Any]] = []
    block = 0
    while not chunks or block < chunks[-1]["block_count"]:
        chunk = review_text(client, review, source_id, block)["text"]
        assert chunk["first_block"] == block
        chunks.append(chunk)
        block = chunk["end_block"]
    return chunks


def _on(review: dict[str, Any]) -> dict[str, Any]:
    return {
        "review_id": review["review_id"], "since": review["revision"],
        "current": review["focus_id"],
    }


# --- chunks give what the whole document gives -------------------------------------------

@pytest.mark.parametrize("source_id", [PILOT, EPISODE])
def test_the_chunks_of_a_source_add_up_to_its_whole_document(
    client: TestClient, source_id: int,
) -> None:
    review = open_review(client, SCOPE)
    whole = _documents(client)[source_id]

    chunks = _chunks(client, review, source_id)

    assert [c["blocks"] for c in chunks] != []
    assert [b for c in chunks for b in c["blocks"]] == whole["blocks"]
    assert [h for c in chunks for h in c["highlights"]] == whole["highlights"]


def test_the_pilot_has_three_chunks_with_overlapping_marks_kept_as_whole(
    client: TestClient, phrase_ids: list[int],
) -> None:
    review = open_review(client, SCOPE)

    chunks = _chunks(client, review, PILOT)

    assert [(c["first_block"], c["end_block"]) for c in chunks] == [
        FIRST_CHUNK, SECOND_CHUNK, LAST_CHUNK,
    ]
    marked = [[h["phrase_id"] for h in c["highlights"]] for c in chunks]
    assert marked == [
        [phrase_ids[GIVE_UP], phrase_ids[PURSUIT]],
        [phrase_ids[WHILE], phrase_ids[GLARE]],
        [phrase_ids[GIVE_UP_LATER], phrase_ids[HOPE]],
    ]
    assert [b.get("number") for c in chunks for b in c["blocks"]] == [
        None, None, 1, 1, 2, None,
    ]


def test_a_chunk_places_itself_in_the_documents_text(client: TestClient) -> None:
    review = open_review(client, SCOPE)
    whole = PILOT_DOCUMENT.text

    for chunk in _chunks(client, review, PILOT):
        blocks = PILOT_DOCUMENT.blocks[chunk["first_block"]:chunk["end_block"]]
        assert whole[chunk["start_offset"]:chunk["end_offset"]] == BLOCK_SEPARATOR.join(
            block_text(b) for b in blocks
        )
        assert (chunk["block_count"], chunk["text_length"]) == (
            len(PILOT_DOCUMENT.blocks), len(whole),
        )


# --- the answer of a text read -------------------------------------------------------------

def test_the_last_block_names_the_last_chunk(client: TestClient) -> None:
    review = open_review(client, SCOPE)

    answer = review_text(client, review, PILOT, LAST_BLOCK)

    assert (answer["text"]["first_block"], answer["text"]["end_block"]) == LAST_CHUNK
    assert answer["layout"] is None
    assert answer["contents_version"] == 0


def test_a_text_read_that_opens_the_current_cards_section_sends_the_rows_anew(
    client: TestClient, phrase_ids: list[int],
) -> None:
    opened = client.post("/api/review", json={"scope": SCOPE}).json()
    folded = {row["section"] for row in opened["layout"]["rows"] if row["kind"] == "section"}
    assert "probably_known" in folded

    answer = review_text(client, opened, PILOT, 0, current=phrase_ids[WHILE])

    assert answer["layout"]["replace"] is True
    assert phrase_ids[WHILE] in {
        row["phrase_id"] for row in answer["layout"]["rows"] if row["kind"] == "card"
    }


@pytest.mark.parametrize(("source_id", "block"), [
    (PILOT, len(PILOT_DOCUMENT.blocks)),
    (99, 0),
    (NOTES, 0),
])
def test_text_the_review_does_not_have_is_404(
    client: TestClient, source_id: int, block: int,
) -> None:
    review = open_review(client, SCOPE)

    response = client.get(
        f"/api/review/{review['review_id']}/text/{source_id}",
        params={"block": block, "since": review["revision"]},
    )

    assert response.status_code == 404, response.text


def test_a_block_before_the_last_one_named_is_422(client: TestClient) -> None:
    review = open_review(client, SCOPE)

    response = client.get(
        f"/api/review/{review['review_id']}/text/{PILOT}",
        params={"block": -2, "since": review["revision"]},
    )

    assert response.status_code == 422


@pytest.mark.parametrize(("path", "params"), [
    ("contents", {}), (f"text/{PILOT}", {"block": 0}),
])
def test_text_of_a_review_no_longer_held_is_410(
    client: TestClient, path: str, params: dict[str, int],
) -> None:
    response = client.get(f"/api/review/gone/{path}", params={"since": 0, **params})

    assert (response.status_code, response.json()["detail"]) == (410, "review_expired")


# --- contents ------------------------------------------------------------------------------

def test_contents_list_the_sources_with_a_document_in_set_order(client: TestClient) -> None:
    review = open_review(client, SCOPE)

    contents = review_contents(client, review)

    assert contents["version"] == 0
    assert [(d["source_id"], d["title"]) for d in contents["documents"]] == [
        (EPISODE, "Episode 2"), (PILOT, "Pilot"),
    ]
    assert list(_documents(client)) == [d["source_id"] for d in contents["documents"]]
    assert all(d["size_hint"] > 0 for d in contents["documents"])


def _changes(client: TestClient, review: dict[str, Any]) -> dict[str, Any]:
    response = client.get(f"/api/review/{review['review_id']}/changes", params={
        "since": review["revision"], "current": review["focus_id"],
    })
    assert response.status_code == 200, response.text
    answer: dict[str, Any] = response.json()
    return answer


def test_the_contents_version_moves_on_when_the_sets_sources_change(
    client: TestClient, factory: sessionmaker[Session],
) -> None:
    review = open_review(client, SCOPE)
    assert review["contents_version"] == 0
    assert _changes(client, review)["contents_version"] == 0

    with factory() as session:
        session.add(SourceModel(
            id=LATER, title="Later", status="done", collection_id=COLLECTION,
            created_at=datetime(2026, 1, 4, tzinfo=UTC),
        ))
        session.flush()
        SqlaDocumentRepository(session).save(LATER, LATER_DOCUMENT)
        session.commit()
    assert LATER not in {d["source_id"] for d in review_contents(client, review)["documents"]}
    assert _changes(client, review)["contents_version"] == 1
    assert _changes(client, review)["contents_version"] == 1
    contents = review_contents(client, review)
    assert contents["version"] == 1
    assert LATER in {d["source_id"] for d in contents["documents"]}

    with factory() as session:
        session.execute(text("UPDATE sources SET collection_id = NULL WHERE id = :id"), {
            "id": EPISODE,
        })
        session.commit()
    assert _changes(client, review)["contents_version"] == 2
    assert EPISODE not in {
        d["source_id"] for d in review_contents(client, review)["documents"]
    }
    response = client.get(
        f"/api/review/{review['review_id']}/text/{EPISODE}",
        params={"block": 0, "since": review["revision"]},
    )
    assert response.status_code == 404


# --- Review Focus: phrases selected on a chunk ----------------------------------------------

def _selection(start: tuple[int, int, int], end: tuple[int, int, int]) -> dict[str, int]:
    return {
        "start_block": start[0], "start_line": start[1], "start_char": start[2],
        "end_block": end[0], "end_line": end[1], "end_char": end[2],
    }


def _stored_position(factory: sessionmaker[Session], phrase_id: int) -> list[int]:
    with factory() as session:
        stored = session.execute(
            text("SELECT phrase_position FROM phrases WHERE id = :id"), {"id": phrase_id},
        ).scalar_one()
    position: list[int] = json.loads(stored)
    return position


def test_a_selection_inside_a_block_of_the_second_chunk_sets_the_phrase(
    client: TestClient, factory: sessionmaker[Session], phrase_ids: list[int],
) -> None:
    review = open_review(client, SCOPE)
    glare = phrase_ids[GLARE]
    assert review_text(client, review, PILOT, 3)["text"]["first_block"] == SECOND_CHUNK[0]

    response = client.put(
        f"/phrases/{glare}/phrase-boundary",
        json={"selection": _selection((3, 0, 5), (3, 0, 21))}, params=_on(review),
    )

    assert response.status_code == 200, response.text
    assert _stored_position(factory, glare) == [3, 0, 5, 0, 21]
    [mark] = [
        h for h in review_text(client, review, PILOT, 3)["text"]["highlights"]
        if h["phrase_id"] == glare
    ]
    assert mark["position"] == {
        "block": 3, "start_line": 0, "start_char": 9, "end_line": 0, "end_char": 15,
    }


def test_a_selection_across_the_chunks_border_is_refused(
    client: TestClient, factory: sessionmaker[Session], phrase_ids: list[int],
) -> None:
    review = open_review(client, SCOPE)
    pursuit = phrase_ids[PURSUIT]
    before = _stored_position(factory, pursuit)

    response = client.put(
        f"/phrases/{pursuit}/phrase-boundary",
        json={"selection": _selection((1, 1, 0), (2, 0, 5))}, params=_on(review),
    )

    assert (response.status_code, response.json()["detail"]) == (400, ONE_BLOCK_MESSAGE)
    assert _stored_position(factory, pursuit) == before


def test_a_word_added_in_the_second_chunk_is_marked_there(client: TestClient) -> None:
    review = open_review(client, SCOPE)

    response = client.post(
        f"/sources/{PILOT}/candidates/manual",
        json={"target_words": [1], "selection": _selection((2, 0, 6), (2, 0, 25))},
        params=_on(review),
    )

    assert response.status_code == 201, response.text
    added = response.json()["focus_id"]
    chunk = review_text(client, review, PILOT, 2, current=added)["text"]
    [mark] = [h for h in chunk["highlights"] if h["phrase_id"] == added]
    assert mark["position"]["block"] == 2
    lingered = PILOT_DOCUMENT.blocks[2]
    assert block_text(lingered)[
        mark["position"]["start_char"]:mark["position"]["end_char"]
    ] == "lingered"


def test_a_word_added_across_two_blocks_is_refused(client: TestClient) -> None:
    review = open_review(client, SCOPE)

    response = client.post(
        f"/sources/{PILOT}/candidates/manual",
        json={"target_words": [0], "selection": _selection((1, 1, 0), (2, 0, 5))},
        params=_on(review),
    )

    assert (response.status_code, response.json()["detail"]) == (400, ONE_BLOCK_MESSAGE)
