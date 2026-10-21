from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from contextlib import AbstractContextManager


class ReviewOrderStore[R](ABC):
    """Where the open reviews are held between requests, each under its id. `R` is what a
    review holds; the store keeps it as it is. A review may be let go at any time (a
    restart, or newer ones pushing it out): the client opens it again."""

    @abstractmethod
    def open(self, review: R) -> str:
        """Holds the review under a new id and gives that id."""

    @abstractmethod
    def hold(self, review_id: str) -> AbstractContextManager[R]:
        """The review, held for the block under its own lock: one request at a time works on
        it. ReviewNotFoundError when no review is held under the id."""

    @abstractmethod
    def pin(self, review_id: str) -> AbstractContextManager[None]:
        """The review stays held for the block, however many newer ones come, without its
        lock: other requests work on it meanwhile. ReviewNotFoundError when no review is
        held under the id."""
