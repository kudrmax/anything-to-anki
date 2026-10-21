"""The open reviews written to disk: a review memory let go, by a restart or newer reviews,
is read back as it was last held; its heavy part is written only when it changes; a review
whose folder is gone, whose id is no folder name or which other code wrote is not held; the
folders over the limit go."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

import pytest
from backend.domain.exceptions import ReviewNotFoundError
from backend.infrastructure.review import file_review_order_store as module
from backend.infrastructure.review.file_review_order_store import (
    HEAVY_FILE,
    LIGHT_FILE,
    REVIEWS_ON_DISK,
    FileReviewOrderStore,
    ReviewCodec,
)
from backend.infrastructure.review.in_memory_review_order_store import InMemoryReviewOrderStore

if TYPE_CHECKING:
    from pathlib import Path


@dataclass
class Review:
    order: list[int]
    current: int | None = None
    order_version: int = 0
    log: list[str] = field(default_factory=list)


class Codec(ReviewCodec[Review]):
    def heavy(self, review: Review) -> object:
        return list(review.order)

    def heavy_mark(self, review: Review) -> int:
        return review.order_version

    def light(self, review: Review) -> object:
        return (review.current, review.order_version)

    def joined(self, heavy: object, light: object) -> Review:
        assert isinstance(heavy, list) and isinstance(light, tuple)
        current, version = light
        return Review(order=heavy, current=current, order_version=version)


def _store(root: Path, capacity: int = 16) -> FileReviewOrderStore[Review]:
    return FileReviewOrderStore(root, Codec(), InMemoryReviewOrderStore(capacity))


def test_a_restart_goes_on_with_the_review_as_it_was_last_held(tmp_path: Path) -> None:
    store = _store(tmp_path)
    review_id = store.open(Review(order=[3, 1, 2]))
    with store.hold(review_id) as review:
        review.current = 1

    restarted = _store(tmp_path)

    with restarted.hold(review_id) as review:
        assert (review.order, review.current) == ([3, 1, 2], 1)
        review.current = 2
    with _store(tmp_path).hold(review_id) as review:
        assert review.current == 2


def test_a_review_newer_ones_pushed_out_of_memory_is_read_back(tmp_path: Path) -> None:
    store = _store(tmp_path, capacity=1)
    first = store.open(Review(order=[1]))
    store.open(Review(order=[2]))

    with store.hold(first) as review:
        assert review.order == [1]


def test_the_heavy_part_is_written_again_only_when_its_mark_moves(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = _store(tmp_path)
    review_id = store.open(Review(order=[1, 2]))
    written: list[str] = []
    write = module._write  # noqa: SLF001

    def spy(path: Path, part: object) -> None:
        written.append(path.name)
        write(path, part)

    monkeypatch.setattr(module, "_write", spy)

    with store.hold(review_id) as review:
        review.current = 2
    assert written == [LIGHT_FILE]

    with store.hold(review_id) as review:
        review.order, review.order_version = [2, 1], 1
    assert written == [LIGHT_FILE, HEAVY_FILE, LIGHT_FILE]
    with _store(tmp_path).hold(review_id) as review:
        assert review.order == [2, 1]


def test_a_review_whose_folder_is_gone_is_not_held(tmp_path: Path) -> None:
    review_id = _store(tmp_path).open(Review(order=[1]))
    (tmp_path / review_id / LIGHT_FILE).unlink()

    with pytest.raises(ReviewNotFoundError):
        _store(tmp_path).hold(review_id).__enter__()


@pytest.mark.parametrize("review_id", ["../escape", "", "a/b", "x" * 65])
def test_an_id_that_is_no_folder_name_is_not_held(tmp_path: Path, review_id: str) -> None:
    with pytest.raises(ReviewNotFoundError):
        _store(tmp_path).hold(review_id).__enter__()


def test_a_review_other_code_wrote_is_not_held(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    review_id = _store(tmp_path).open(Review(order=[1]))
    monkeypatch.setattr(module, "_digest", lambda _modules: b"other code")

    with pytest.raises(ReviewNotFoundError):
        _store(tmp_path).hold(review_id).__enter__()


def test_the_folders_over_the_limit_go_least_recently_written_first(tmp_path: Path) -> None:
    store = _store(tmp_path)
    ids = [store.open(Review(order=[i])) for i in range(REVIEWS_ON_DISK)]
    with store.hold(ids[0]):
        pass

    store.open(Review(order=[-1]))

    folders = {f.name for f in tmp_path.iterdir()}
    assert ids[0] in folders
    assert ids[1] not in folders
    assert len(folders) == REVIEWS_ON_DISK
