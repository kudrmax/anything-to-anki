"""The review list as the screen reads it through the window API: a review opened with every
section open, then every row of it in pages of REVIEW_ROWS_MAX."""
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
    """Every card of the set's review in row order, as the card JSON the rows send: its
    `section` is the section the review holds it in."""
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
