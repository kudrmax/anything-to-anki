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
    pins: int = 0


class InMemoryReviewOrderStore[R](ReviewOrderStore[R]):
    """The open reviews in the app's memory, at most `capacity` of them besides the pinned
    ones: the one held least recently goes first. A restart lets every one go."""

    def __init__(self, capacity: int = REVIEWS_KEPT) -> None:
        self._capacity = capacity
        self._reviews: OrderedDict[str, _Held[R]] = OrderedDict()
        self._lock = threading.Lock()

    def open(self, review: R) -> str:
        review_id = secrets.token_urlsafe(_ID_BYTES)
        with self._lock:
            self._reviews[review_id] = _Held(review)
            self._let_go()
        return review_id

    def keep(self, review_id: str, review: R) -> None:
        """Holds the review under an id it had before, unless one is held there already."""
        with self._lock:
            if review_id not in self._reviews:
                self._reviews[review_id] = _Held(review)
                self._let_go()

    def holds(self, review_id: str) -> bool:
        with self._lock:
            return review_id in self._reviews

    @contextmanager
    def hold(self, review_id: str) -> Iterator[R]:
        held = self._used(review_id)
        with held.lock:
            yield held.review

    @contextmanager
    def pin(self, review_id: str) -> Iterator[None]:
        with self._lock:
            held = self._used_locked(review_id)
            held.pins += 1
        try:
            yield
        finally:
            with self._lock:
                held.pins -= 1
                self._let_go()

    def _used(self, review_id: str) -> _Held[R]:
        with self._lock:
            return self._used_locked(review_id)

    def _used_locked(self, review_id: str) -> _Held[R]:
        held = self._reviews.get(review_id)
        if held is None:
            raise ReviewNotFoundError(review_id)
        self._reviews.move_to_end(review_id)
        return held

    def _let_go(self) -> None:
        """The least recently held reviews over the capacity go; a pinned one neither goes
        nor counts."""
        loose = [rid for rid, held in self._reviews.items() if not held.pins]
        for review_id in loose[:max(0, len(loose) - self._capacity)]:
            del self._reviews[review_id]
