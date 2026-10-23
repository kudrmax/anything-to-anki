"""Picture searches apart from requests: a request reads how a search stands and never
waits for it."""
from __future__ import annotations

import threading
import time

import pytest
from backend.domain.exceptions import ImageSearchError
from backend.domain.value_objects.image_option import ImageOption
from backend.domain.value_objects.image_provider import ImageProvider
from backend.domain.value_objects.picture_search import PictureSearch, PictureSearchStatus
from backend.infrastructure.services.threaded_picture_searches import ThreadedPictureSearches

pytestmark = pytest.mark.unit

PICTURE = ImageOption(url="https://pictures/ladder.jpg", provider=ImageProvider.BING)
WAIT_S = 5.0


class _Clock:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now


def _settled(searches: ThreadedPictureSearches, key: str) -> PictureSearch:
    deadline = time.monotonic() + WAIT_S
    while (state := searches.search(key, _never)).status is PictureSearchStatus.SEARCHING:
        assert time.monotonic() < deadline, "the search never ended"
        time.sleep(0.01)
    return state


def _never() -> list[ImageOption]:
    raise AssertionError("a known search does not run again")


def test_the_first_ask_answers_at_once_while_the_search_runs() -> None:
    searches = ThreadedPictureSearches()
    release = threading.Event()

    def slow() -> list[ImageOption]:
        release.wait(WAIT_S)
        return [PICTURE]

    started = time.monotonic()
    first = searches.search("ladder", slow)
    assert time.monotonic() - started < 1.0
    assert first.status is PictureSearchStatus.SEARCHING
    assert searches.search("ladder", _never).status is PictureSearchStatus.SEARCHING

    release.set()
    assert _settled(searches, "ladder") == PictureSearch(PictureSearchStatus.READY, (PICTURE,))
    searches.close()


def test_a_failed_search_is_failed_and_runs_again_only_after_a_while() -> None:
    clock = _Clock()
    searches = ThreadedPictureSearches(retry_after_s=60.0, monotonic=clock)

    def failing() -> list[ImageOption]:
        raise ImageSearchError("down")

    searches.search("ladder", failing)
    assert _settled(searches, "ladder").status is PictureSearchStatus.FAILED

    clock.now = 30.0
    assert searches.search("ladder", _never).status is PictureSearchStatus.FAILED
    clock.now = 61.0
    assert searches.search("ladder", lambda: [PICTURE]).status is PictureSearchStatus.SEARCHING
    assert _settled(searches, "ladder").options == (PICTURE,)
    searches.close()


def test_a_broken_search_ends_as_failed_rather_than_searching_for_ever() -> None:
    searches = ThreadedPictureSearches()

    def broken() -> list[ImageOption]:
        raise RuntimeError("bug")

    searches.search("ladder", broken)
    assert _settled(searches, "ladder").status is PictureSearchStatus.FAILED
    searches.close()


def test_no_more_searches_run_at_once_than_its_workers() -> None:
    searches = ThreadedPictureSearches(workers=2)
    release = threading.Event()
    lock = threading.Lock()
    running = [0]
    most = [0]

    def slow() -> list[ImageOption]:
        with lock:
            running[0] += 1
            most[0] = max(most[0], running[0])
        release.wait(WAIT_S)
        with lock:
            running[0] -= 1
        return []

    for word in range(6):
        searches.search(f"w{word}", slow)
    time.sleep(0.2)
    release.set()
    for word in range(6):
        _settled(searches, f"w{word}")
    assert most[0] == 2
    searches.close()


def test_it_remembers_only_the_most_recently_asked_searches() -> None:
    searches = ThreadedPictureSearches(kept=2)
    for word in ("a", "b"):
        searches.search(word, lambda: [PICTURE])
        _settled(searches, word)
    searches.search("a", _never)
    searches.search("c", lambda: [PICTURE])
    _settled(searches, "c")

    assert searches.search("a", _never).status is PictureSearchStatus.READY
    assert searches.search("b", lambda: []).status is PictureSearchStatus.SEARCHING
    searches.close()
