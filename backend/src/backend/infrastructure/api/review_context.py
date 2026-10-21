"""What every request on an open review names, and how a review no longer held answers."""
from __future__ import annotations

from contextlib import contextmanager
from typing import TYPE_CHECKING

from fastapi import HTTPException

from backend.application.dto.review_dtos import ReviewContext
from backend.domain.exceptions import ReviewNotFoundError

if TYPE_CHECKING:
    from collections.abc import Iterator

# The detail of a 410: the review is not held any more and the client opens it again.
REVIEW_EXPIRED = "review_expired"


def review_context(review_id: str, since: int, current: int | None = None) -> ReviewContext:
    """The review, the client's revision and the card it shows."""
    return ReviewContext(review_id=review_id, since=since, current=current)


@contextmanager
def review_expired() -> Iterator[None]:
    """A review no longer held is a 410 the client opens it again on."""
    try:
        yield
    except ReviewNotFoundError as e:
        raise HTTPException(status_code=410, detail=REVIEW_EXPIRED) from e
