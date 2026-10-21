"""An open review on the server: its order held under a review id, its visible list sent in
windows with full cards only for the rows sent, and a review the server let go opened again
on the same card (Review Focus 4 and 5), through the use cases and the routes."""
from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from backend.application.constants import REVIEW_ROWS_MAX, REVIEW_WINDOW_AROUND
from backend.application.dto.review_dtos import OpenReviewRequest, ReviewContext
from backend.application.utils.card_views import CardViews
from backend.domain.value_objects.candidate_section import CandidateSection
from backend.domain.value_objects.candidate_sort_order import CandidateSortOrder
from backend.domain.value_objects.card_choice import Press
from backend.domain.value_objects.review_order import SectionRow
from backend.domain.value_objects.source_scope import SourceScope
from backend.infrastructure.api.app import app
from backend.infrastructure.api.dependencies import (
    get_container,
    get_db_session,
    get_session_factory,
)
from backend.infrastructure.persistence.database import Base, _enable_sqlite_foreign_keys
from backend.infrastructure.review.in_memory_review_order_store import InMemoryReviewOrderStore
from fastapi.testclient import TestClient
from sqlalchemy import StaticPool, create_engine, event, text
from sqlalchemy.orm import Session, sessionmaker

from tests.integration.conftest import insert_source
from tests.projection_support import rebuild_projection
from tests.word_support import KNOWN, insert_word, phrase_id_of

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator, Sequence

    from backend.application.dto.review_dtos import ReviewUpdateDTO
    from backend.application.dto.source_dtos import CardDTO
    from backend.application.utils.open_review import OpenReview

pytestmark = pytest.mark.integration

COLLECTION = 7
SOURCES = (1, 2, 3)
WORDS_PER_SOURCE = 80
CARDS = len(SOURCES) * WORDS_PER_SOURCE
# Every fifth word is an interjection: probably known. Every seventh is known: reviewed.
JUNK_EVERY, KNOWN_EVERY = 5, 7
SCOPE = str(COLLECTION)


def _word_ids(source_id: int) -> range:
    first = (source_id - 1) * WORDS_PER_SOURCE + 1
    return range(first, first + WORDS_PER_SOURCE)


@pytest.fixture()
def factory() -> Iterator[sessionmaker[Session]]:
    engine = create_engine(
        "sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool,
    )
    event.listen(engine, "connect", _enable_sqlite_foreign_keys)
    Base.metadata.create_all(engine)
    made = sessionmaker(bind=engine)
    with made() as session:
        session.execute(text(
            "INSERT INTO collections (id, name, position, created_at)"
            " VALUES (:id, 'Show', 0, '2026-01-01 00:00:00')"
        ), {"id": COLLECTION})
        for source_id in SOURCES:
            insert_source(session, source_id)
            session.execute(text("UPDATE sources SET collection_id = :c WHERE id = :s"), {
                "c": COLLECTION, "s": source_id,
            })
            for word_id in _word_ids(source_id):
                insert_word(
                    session, word_id, source_id=source_id,
                    pos="INTJ" if word_id % JUNK_EVERY == 0 else "NOUN",
                    status=KNOWN if word_id % KNOWN_EVERY == 0 else "pending",
                )
        session.commit()
        rebuild_projection(session)
    yield made
    engine.dispose()


@pytest.fixture()
def client(factory: sessionmaker[Session]) -> Iterator[TestClient]:
    def override_session() -> Iterator[Session]:
        with factory() as session:
            yield session

    app.dependency_overrides[get_db_session] = override_session
    app.dependency_overrides[get_session_factory] = lambda: factory
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture()
def restart() -> Iterator[Callable[[], None]]:
    """Lets every open review go, as a restart does; the app's store comes back after."""
    container = get_container()
    kept = container._review_order_store  # noqa: SLF001

    def let_go() -> None:
        container._review_order_store = InMemoryReviewOrderStore()  # noqa: SLF001

    yield let_go
    container._review_order_store = kept  # noqa: SLF001


def _open(
    factory: sessionmaker[Session],
    sort: CandidateSortOrder = CandidateSortOrder.RELEVANCE,
    **request: object,
) -> ReviewUpdateDTO:
    with factory() as session:
        return get_container().open_review_use_case(session).execute(
            OpenReviewRequest(scope=SCOPE, sort=sort, **request),  # type: ignore[arg-type]
        )


def _held(review_id: str) -> OpenReview:
    with get_container()._review_order_store.hold(review_id) as review:  # noqa: SLF001
        return review


def _last_source(factory: sessionmaker[Session]) -> int:
    with factory() as session:
        sources = get_container()._scope_resolver(session).reviewable_sources(  # noqa: SLF001
            SourceScope.collection(COLLECTION),
        )
    last = sources[-1].id
    assert last is not None
    return last


# --- Review Focus 4: a far card brings only its window ----------------------------------

def test_around_a_card_of_the_last_source_sends_only_its_window(
    factory: sessionmaker[Session], monkeypatch: pytest.MonkeyPatch,
) -> None:
    opened = _open(factory, CandidateSortOrder.CHRONOLOGICAL)
    last = _last_source(factory)
    target = phrase_id_of(_word_ids(last)[WORDS_PER_SOURCE // 2])
    asked: list[list[int]] = []
    of_phrases = CardViews.of_phrases

    def spied(
        self: CardViews, phrase_ids: Sequence[int], sections: dict[int, CandidateSection],
    ) -> list[CardDTO]:
        asked.append(list(phrase_ids))
        return of_phrases(self, phrase_ids, sections)

    monkeypatch.setattr(CardViews, "of_phrases", spied)
    with factory() as session:
        update = get_container().review_window_use_case(session).around(
            ReviewContext(opened.review_id, opened.revision, opened.focus_id), target,
        )

    layout = update.layout
    assert layout is not None
    assert (layout.total_rows, layout.total_cards, layout.replace) == (CARDS, CARDS, False)
    target_row = next(row for row in layout.rows if row.phrase_id == target)
    indices = [row.index for row in layout.rows]
    assert indices == list(range(
        target_row.index - REVIEW_WINDOW_AROUND,
        min(target_row.index + REVIEW_WINDOW_AROUND + 1, CARDS),
    ))
    window = [row.phrase_id for row in layout.rows]
    assert len(update.cards) <= 2 * REVIEW_WINDOW_AROUND + 1
    assert asked == [window]
    assert [card.phrase_id for card in update.cards] == window
    assert update.focus_id == target
    # The rows before the window were never sent: only the opening's and this window were.
    first = opened.layout
    assert first is not None
    served = _held(opened.review_id).served
    assert served == {row.phrase_id for row in first.rows} | set(window)
    assert min(indices) > max(row.index for row in first.rows)


def test_a_review_keeps_its_order_while_cards_are_decided(
    factory: sessionmaker[Session],
) -> None:
    opened = _open(factory, CandidateSortOrder.CHRONOLOGICAL)
    order = [card.phrase_id for card in _held(opened.review_id).order.cards]
    with factory() as session:
        get_container().decide_phrase_use_case(session).decide(order[0], Press.KNOWN)
        update = get_container().review_window_use_case(session).rows(
            ReviewContext(opened.review_id, opened.revision, opened.focus_id), 0, 5,
        )
    assert update.layout is not None
    assert [row.phrase_id for row in update.layout.rows] == order[:5]
    assert update.revision > opened.revision


# --- Review Focus 5: a review the server let go opens again on the same card --------------

def test_a_review_let_go_opens_again_on_its_card_with_its_sections(
    client: TestClient, restart: Callable[[], None],
) -> None:
    opened = client.post("/api/review", json={
        "scope": SCOPE, "open_sections": ["reviewed"],
    }).json()
    review_id = opened["review_id"]
    folded = next(
        card.phrase_id for card in _held(review_id).order.cards
        if card.section is CandidateSection.PROBABLY_KNOWN
    )
    around = client.get(f"/api/review/{review_id}/around/{folded}", params={
        "since": opened["revision"], "current": opened["focus_id"],
    }).json()
    assert around["layout"]["replace"] is True
    assert _section_rows(review_id) == {"probably_known": True, "reviewed": True}

    restart()

    for answer in (
        client.get(f"/api/review/{review_id}/rows", params={
            "start": 0, "count": 10, "since": opened["revision"], "current": folded,
        }),
        client.get(f"/api/review/{review_id}/changes", params={
            "since": opened["revision"], "current": folded,
        }),
    ):
        assert (answer.status_code, answer.json()["detail"]) == (410, "review_expired")

    again = client.post("/api/review", json={
        "scope": SCOPE, "requested_id": folded, "open_sections": ["reviewed"],
    }).json()
    assert again["review_id"] != review_id
    assert again["focus_id"] == folded
    assert _section_rows(again["review_id"]) == {"probably_known": True, "reviewed": True}
    assert folded in {row["phrase_id"] for row in again["layout"]["rows"]}
    assert _held(again["review_id"]).opened == frozenset({CandidateSection.REVIEWED})


def _section_rows(review_id: str) -> dict[str, bool]:
    """The section rows of the review's visible list, open or not."""
    return {
        row.section.value: row.open for row in _held(review_id).layout().rows
        if isinstance(row, SectionRow)
    }


# --- the routes -----------------------------------------------------------------------

def test_opening_answers_the_header_the_focus_and_its_window(client: TestClient) -> None:
    answer = client.post("/api/review", json={"scope": SCOPE})
    assert answer.status_code == 200
    update = answer.json()
    assert update["header"]["scope"] == SCOPE
    today = client.get("/api/review", params={"scope": SCOPE}).json()
    assert update["header"]["progress"] == today["progress"]
    layout = update["layout"]
    assert (layout["version"], layout["replace"]) == (0, True)
    assert layout["rows"][0] == {
        "index": 0, "kind": "card", "phrase_id": update["focus_id"], "position": 1,
        "section": None, "count": None, "open": None,
    }
    cards = [row["phrase_id"] for row in layout["rows"] if row["kind"] == "card"]
    assert [card["phrase_id"] for card in update["cards"]] == cards
    assert all(card["section"] == "ready" for card in update["cards"])
    assert (update["removed"], update["done"]) == ([], {})


def test_opening_names_a_set_as_review_does(client: TestClient) -> None:
    assert client.post("/api/review", json={"scope": "garbage"}).status_code == 400
    assert client.post("/api/review", json={"scope": "unsorted"}).status_code == 400
    assert client.post("/api/review", json={"scope": "source-99"}).status_code == 404
    assert client.post("/api/review", json={"scope": "99"}).status_code == 404
    assert client.post("/api/review", json={"scope": SCOPE, "sort": "nope"}).status_code == 422


def test_rows_are_capped(client: TestClient) -> None:
    opened = client.post("/api/review", json={
        "scope": SCOPE, "sort": "chronological",
    }).json()
    rows = client.get(f"/api/review/{opened['review_id']}/rows", params={
        "start": 0, "count": 10 * REVIEW_ROWS_MAX, "since": opened["revision"],
    })
    assert rows.status_code == 200
    layout = rows.json()["layout"]
    assert [row["index"] for row in layout["rows"]] == list(range(REVIEW_ROWS_MAX))
    assert layout["replace"] is False
    past_the_end = client.get(f"/api/review/{opened['review_id']}/rows", params={
        "start": CARDS + 5, "count": 10, "since": opened["revision"],
    }).json()
    assert past_the_end["layout"]["rows"] == []
    for bad in ({"start": -1, "count": 10}, {"start": 0, "count": 0}, {"start": 0}):
        answer = client.get(f"/api/review/{opened['review_id']}/rows", params={
            **bad, "since": opened["revision"],
        })
        assert answer.status_code == 422, bad


def test_a_card_the_review_does_not_hold_is_404(client: TestClient) -> None:
    opened = client.post("/api/review", json={"scope": SCOPE}).json()
    answer = client.get(f"/api/review/{opened['review_id']}/around/999999", params={
        "since": opened["revision"],
    })
    assert answer.status_code == 404


def test_an_unknown_review_is_410_on_every_route(client: TestClient) -> None:
    params = {"since": 0}
    for answer in (
        client.get("/api/review/unknown/rows", params={**params, "start": 0, "count": 5}),
        client.get(f"/api/review/unknown/around/{phrase_id_of(1)}", params=params),
        client.put("/api/review/unknown/sections/extra", params=params, json={"open": True}),
        client.get("/api/review/unknown/changes", params=params),
    ):
        assert (answer.status_code, answer.json()["detail"]) == (410, "review_expired")


def test_opening_a_section_sends_the_window_around_the_card_anew(client: TestClient) -> None:
    opened = client.post("/api/review", json={"scope": SCOPE}).json()
    review_id = opened["review_id"]
    scrolled = client.get(f"/api/review/{review_id}/rows", params={
        "start": 100, "count": 20, "since": opened["revision"], "current": opened["focus_id"],
    }).json()
    assert scrolled["layout"]["replace"] is False
    put = client.put(f"/api/review/{review_id}/sections/probably_known", params={
        "since": opened["revision"], "current": opened["focus_id"],
    }, json={"open": True})
    assert put.status_code == 200
    layout = put.json()["layout"]
    assert (layout["version"], layout["replace"]) == (1, True)
    assert layout["total_rows"] > opened["layout"]["total_rows"]
    assert layout["rows"] == opened["layout"]["rows"]
    window = [row["phrase_id"] for row in layout["rows"] if row["kind"] == "card"]
    assert [card["phrase_id"] for card in put.json()["cards"]] == window
    assert _held(review_id).served == set(window)

    again = client.put(f"/api/review/{review_id}/sections/probably_known", params={
        "since": opened["revision"], "current": opened["focus_id"],
    }, json={"open": True}).json()
    assert (again["layout"]["version"], again["layout"]["replace"]) == (1, False)
    assert again["layout"]["rows"] == []
    assert client.put(f"/api/review/{review_id}/sections/nope", params={
        "since": 0,
    }, json={"open": True}).status_code == 422


def test_moving_between_shown_cards_changes_no_rows(client: TestClient) -> None:
    opened = client.post("/api/review", json={
        "scope": SCOPE, "open_sections": ["probably_known"],
    }).json()
    review_id = opened["review_id"]
    order = _held(review_id).order.cards
    ready = next(c.phrase_id for c in order if c.section is CandidateSection.READY)
    junk = next(c.phrase_id for c in order if c.section is CandidateSection.PROBABLY_KNOWN)
    for current in (junk, ready, None, junk):
        params = {"since": opened["revision"]}
        if current is not None:
            params["current"] = current
        answer = client.get(f"/api/review/{review_id}/changes", params=params).json()
        assert answer["layout"] is None, current
    rows = client.get(f"/api/review/{review_id}/rows", params={
        "start": 0, "count": 5, "since": opened["revision"], "current": ready,
    }).json()["layout"]
    assert (rows["version"], rows["replace"]) == (0, False)


def test_a_set_gone_since_the_opening_is_404(
    client: TestClient, factory: sessionmaker[Session],
) -> None:
    opened = client.post("/api/review", json={"scope": f"source-{SOURCES[0]}"}).json()
    review_id, focus = opened["review_id"], opened["focus_id"]
    with factory() as session:
        session.execute(text("DELETE FROM sources WHERE id = :id"), {"id": SOURCES[0]})
        session.commit()
    params = {"since": opened["revision"], "current": focus}
    for answer in (
        client.get(f"/api/review/{review_id}/rows", params={**params, "start": 0, "count": 5}),
        client.get(f"/api/review/{review_id}/changes", params=params),
        client.get(f"/api/review/{review_id}/around/{focus}", params=params),
    ):
        assert answer.status_code == 404


def test_changes_answer_the_header_and_revision(client: TestClient) -> None:
    opened = client.post("/api/review", json={"scope": SCOPE}).json()
    changes = client.get(f"/api/review/{opened['review_id']}/changes", params={
        "since": opened["revision"], "current": opened["focus_id"],
    })
    assert changes.status_code == 200
    body = changes.json()
    assert (body["revision"], body["layout"], body["cards"]) == (opened["revision"], None, [])
    assert body["header"] == opened["header"]
    assert client.get(f"/api/review/{opened['review_id']}/changes").status_code == 422
