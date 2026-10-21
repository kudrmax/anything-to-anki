"""The review list as the screen reads it through the window API: a review opened with every
section open, then every row of it in pages of REVIEW_ROWS_MAX; the contents of its set and
chunks of its text."""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

from backend.application.constants import REVIEW_ROWS_MAX

from tests.review_support import ALL_SECTIONS

if TYPE_CHECKING:
    from fastapi.testclient import TestClient

CARD_ROW = "card"


# Any: the raw JSON of the API, as the test reads it.
def open_review(client: TestClient, scope: str, sort: str = "relevance") -> dict[str, Any]:
    """The answer of opening a review of the set with every section open: its `review_id`
    and `revision` are what a change on it sends."""
    response = client.post("/api/review", json={
        "scope": scope, "sort": sort, "open_sections": ALL_SECTIONS,
    })
    assert response.status_code == 200, response.text
    opened: dict[str, Any] = response.json()
    return opened


# Any: the raw JSON of the API, as the test reads it.
def review_list(
    client: TestClient, scope: str, sort: str = "relevance",
) -> list[dict[str, Any]]:
    """Every card of the set's review in row order, each with the section the review holds
    it in."""
    opened = open_review(client, scope, sort)
    layout = opened["layout"]
    rows: list[dict[str, Any]] = []
    cards: dict[int, dict[str, Any]] = {}
    for start in range(0, layout["total_rows"], REVIEW_ROWS_MAX):
        response = client.get(f"/api/review/{opened['review_id']}/rows", params={
            "start": start, "count": REVIEW_ROWS_MAX, "since": opened["revision"],
        })
        assert response.status_code == 200, response.text
        page = response.json()
        assert page["layout"]["replace"] is False
        rows += page["layout"]["rows"]
        cards |= {card["phrase_id"]: card for card in page["cards"]}
    assert [row["index"] for row in rows] == list(range(layout["total_rows"]))
    listed = [cards[row["phrase_id"]] for row in rows if row["kind"] == CARD_ROW]
    assert len(listed) == layout["total_cards"]
    return listed


# Any: the raw JSON of the API, as the test reads it.
def _on_review(review: dict[str, Any], current: int | None) -> dict[str, Any]:
    params = {"since": review["revision"], "current": current}
    return {k: v for k, v in params.items() if v is not None}


# Any: the raw JSON of the API, as the test reads it.
def review_contents(client: TestClient, review: dict[str, Any]) -> dict[str, Any]:
    """The contents of the open review's set."""
    response = client.get(
        f"/api/review/{review['review_id']}/contents",
        params=_on_review(review, review["focus_id"]),
    )
    assert response.status_code == 200, response.text
    contents: dict[str, Any] = response.json()
    return contents


# Any: the raw JSON of the API, as the test reads it.
def review_text(
    client: TestClient, review: dict[str, Any], source_id: int, block: int,
    current: int | None = None,
) -> dict[str, Any]:
    """The answer with the chunk of the source's text that holds the block; the client shows
    `current`, else the review's focus."""
    response = client.get(
        f"/api/review/{review['review_id']}/text/{source_id}",
        params={"block": block, **_on_review(review, current or review["focus_id"])},
    )
    assert response.status_code == 200, response.text
    answer: dict[str, Any] = response.json()
    return answer
