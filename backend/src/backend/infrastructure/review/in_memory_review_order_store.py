from __future__ import annotations

import secrets
import threading
from collections import OrderedDict
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from backend.domain.exceptions import ReviewNotFoundError
from backend.domain.ports.review_order_store import ReviewOrderStore

if TYPE_CHECKING:
    from collections.abc import Iterator

# Enough for every tab of one user; a whole book's review holds a few megabytes.
REVIEWS_KEPT = 16
_ID_BYTES = 16


@dataclass
class _Held[R]:
    review: R
    lock: threading.Lock = field(default_factory=threading.Lock)


class InMemoryReviewOrderStore[R](ReviewOrderStore[R]):
    """The open reviews in the app's memory, at most `capacity` of them: the one held least
    recently goes first. A restart lets every one go."""

    def __init__(self, capacity: int = REVIEWS_KEPT) -> None:
        self._capacity = capacity
        self._reviews: OrderedDict[str, _Held[R]] = OrderedDict()
        self._lock = threading.Lock()

    def open(self, review: R) -> str:
        review_id = secrets.token_urlsafe(_ID_BYTES)
        with self._lock:
            self._reviews[review_id] = _Held(review)
            while len(self._reviews) > self._capacity:
                self._reviews.popitem(last=False)
        return review_id

    @contextmanager
    def hold(self, review_id: str) -> Iterator[R]:
        with self._lock:
            held = self._reviews.get(review_id)
            if held is None:
                raise ReviewNotFoundError(review_id)
            self._reviews.move_to_end(review_id)
        with held.lock:
            yield held.review
