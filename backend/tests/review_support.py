"""The open review a review screen's change names: a stand-in for route unit tests, and a
review opened through the API for the ones on a real app."""
from __future__ import annotations

from typing import TYPE_CHECKING, Any
from urllib.parse import parse_qsl

from backend.application.dto.review_dtos import ReviewHeaderDTO, ReviewUpdateDTO
from backend.application.dto.source_dtos import ProgressDTO

if TYPE_CHECKING:
    from collections.abc import Callable

    from backend.application.dto.review_dtos import ReviewContext
    from backend.application.dto.source_dtos import CardDTO
    from fastapi.testclient import TestClient
    from httpx import Response

# What a change on an open review sends besides its own body.
REVIEW_PARAMS: dict[str, str | int] = {"review_id": "review", "since": 0}


def empty_update(review_id: str) -> ReviewUpdateDTO:
    return ReviewUpdateDTO(
        review_id=review_id,
        revision=0,
        header=ReviewHeaderDTO(
            scope="all", title="", status="", progress=ProgressDTO(decided=0, total=0),
            learn_count=0, busy=False, ai_unavailable=False,
        ),
    )


class RunningMutation:
    """ReviewMutation for a container whose use cases are mocks: it runs the action and
    answers that nothing changed."""

    def press(
        self, ctx: ReviewContext, phrase_id: int, action: Callable[[], object],
    ) -> ReviewUpdateDTO:
        del phrase_id
        action()
        return empty_update(ctx.review_id)

    def replace(
        self, ctx: ReviewContext, old_id: int, action: Callable[[], CardDTO],
    ) -> ReviewUpdateDTO:
        del old_id
        action()
        return empty_update(ctx.review_id)

    def add(self, ctx: ReviewContext, action: Callable[[], CardDTO]) -> ReviewUpdateDTO:
        action()
        return empty_update(ctx.review_id)

    def edit[T](
        self, ctx: ReviewContext, action: Callable[[], T],
    ) -> tuple[T, ReviewUpdateDTO]:
        return action(), empty_update(ctx.review_id)


# Every section open: every card of a small set is a row the review serves.
ALL_SECTIONS = ["ready", "extra", "probably_known", "reviewed"]


def open_review(
    client: TestClient, scope: str = "all", *, current: int | None = None,
) -> dict[str, str | int]:
    """A review of the set opened on the app with every section open, on `current` when
    given, as the params a change on it sends."""
    response = client.post("/api/review", json={
        "scope": scope, "requested_id": current, "open_sections": ALL_SECTIONS,
    })
    assert response.status_code == 200, response.text
    opened = response.json()
    params: dict[str, str | int] = {"review_id": opened["review_id"], "since": opened["revision"]}
    if current is not None:
        params["current"] = current
    return params


def on_review(
    client: TestClient,
    method: str,
    path: str,
    *,
    scope: str = "all",
    current: int | None = None,
    params: dict[str, str | int] | None = None,
    **kwargs: Any,  # noqa: ANN401 — whatever TestClient.request takes besides
) -> Response:
    """A change sent on a review of the set opened just before it; a query in `path` is
    sent too."""
    route, _, query = path.partition("?")
    return client.request(
        method, route,
        params={
            **open_review(client, scope, current=current), **dict(parse_qsl(query)),
            **(params or {}),
        },
        **kwargs,
    )


# Any: a JSON answer as the test reads it.
def card_in(update: dict[str, Any], phrase_id: int) -> dict[str, Any]:
    """The full card of the phrase an update sent."""
    return next(card for card in update["cards"] if card["phrase_id"] == phrase_id)
