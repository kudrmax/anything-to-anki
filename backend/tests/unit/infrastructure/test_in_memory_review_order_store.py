"""The open reviews held in memory: the least recently held goes first once the store is
full, an id it does not hold is refused, and one review serves one request at a time."""
from __future__ import annotations

import threading
import time

import pytest
from backend.domain.exceptions import ReviewNotFoundError
from backend.infrastructure.review.in_memory_review_order_store import (
    REVIEWS_KEPT,
    InMemoryReviewOrderStore,
)

HELD_FOR_S = 0.05


def test_the_seventeenth_review_lets_the_least_recently_held_go() -> None:
    store: InMemoryReviewOrderStore[str] = InMemoryReviewOrderStore()
    ids = [store.open(f"review {i}") for i in range(REVIEWS_KEPT)]
    with store.hold(ids[0]):
        pass

    newest = store.open("review 16")

    with pytest.raises(ReviewNotFoundError):
        store.hold(ids[1]).__enter__()
    for review_id in (ids[0], *ids[2:], newest):
        with store.hold(review_id) as review:
            assert review.startswith("review")


def test_an_id_it_does_not_hold_is_refused() -> None:
    store: InMemoryReviewOrderStore[str] = InMemoryReviewOrderStore()
    store.open("review")
    with pytest.raises(ReviewNotFoundError) as refused:
        store.hold("unknown").__enter__()
    assert refused.value.review_id == "unknown"


def test_every_review_gets_its_own_id() -> None:
    store: InMemoryReviewOrderStore[str] = InMemoryReviewOrderStore()
    assert len({store.open("review") for _ in range(REVIEWS_KEPT)}) == REVIEWS_KEPT


def test_two_threads_holding_one_review_take_turns() -> None:
    store: InMemoryReviewOrderStore[list[str]] = InMemoryReviewOrderStore()
    review_id = store.open([])

    def work(name: str) -> None:
        with store.hold(review_id) as log:
            log.append(f"{name} in")
            time.sleep(HELD_FOR_S)
            log.append(f"{name} out")

    threads = [threading.Thread(target=work, args=(name,)) for name in ("a", "b")]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    with store.hold(review_id) as log:
        assert [entry.split()[1] for entry in log] == ["in", "out", "in", "out"]
        assert log[0].split()[0] == log[1].split()[0]


def test_another_review_is_not_held_up() -> None:
    store: InMemoryReviewOrderStore[str] = InMemoryReviewOrderStore()
    first, second = store.open("first"), store.open("second")
    with store.hold(first), store.hold(second) as review:
        assert review == "second"
