from __future__ import annotations

import logging
import time
from collections import OrderedDict, deque
from dataclasses import dataclass
from threading import Condition, Thread
from typing import TYPE_CHECKING

from backend.domain.exceptions import ImageSearchError
from backend.domain.ports.background_picture_searches import BackgroundPictureSearches
from backend.domain.value_objects.picture_search import PictureSearch, PictureSearchStatus

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence

    from backend.domain.value_objects.image_option import ImageOption

logger = logging.getLogger(__name__)

# Searches at once: the picture sources are slow, and the review must keep the server.
PICTURE_SEARCH_WORKERS = 2
# Searches remembered, the least recently asked for go first.
KEPT_PICTURE_SEARCHES = 2_000
# A failed search runs again when asked for after this long.
FAILED_PICTURE_SEARCH_RETRY_S = 300.0

_SEARCHING = PictureSearch(PictureSearchStatus.SEARCHING)


@dataclass(frozen=True)
class _Held:
    search: PictureSearch
    at: float


class ThreadedPictureSearches(BackgroundPictureSearches):
    """Picture searches on a few threads of their own, remembered for the app's life. The
    newest asked search runs first: it is the card on screen, the older ones were for cards
    the user has moved past."""

    def __init__(
        self,
        workers: int = PICTURE_SEARCH_WORKERS,
        kept: int = KEPT_PICTURE_SEARCHES,
        retry_after_s: float = FAILED_PICTURE_SEARCH_RETRY_S,
        monotonic: Callable[[], float] = time.monotonic,
    ) -> None:
        self._kept = kept
        self._retry_after_s = retry_after_s
        self._monotonic = monotonic
        self._changed = Condition()
        self._held: OrderedDict[str, _Held] = OrderedDict()
        self._waiting: deque[tuple[str, Callable[[], Sequence[ImageOption]]]] = deque()
        self._closed = False
        for number in range(workers):
            Thread(target=self._work, name=f"picture-search-{number}", daemon=True).start()

    def search(self, key: str, find: Callable[[], Sequence[ImageOption]]) -> PictureSearch:
        with self._changed:
            held = self._held.get(key)
            if held is not None and not self._due_again(held):
                self._held.move_to_end(key)
                return held.search
            self._held[key] = _Held(_SEARCHING, self._monotonic())
            self._held.move_to_end(key)
            while len(self._held) > self._kept:
                self._held.popitem(last=False)
            self._waiting.append((key, find))
            self._changed.notify()
        return _SEARCHING

    def close(self) -> None:
        """Searches not started are dropped; running ones finish on their own."""
        with self._changed:
            self._closed = True
            self._waiting.clear()
            self._changed.notify_all()

    def _work(self) -> None:
        while True:
            with self._changed:
                while not self._waiting and not self._closed:
                    self._changed.wait()
                if self._closed:
                    return
                key, find = self._waiting.pop()
                if key not in self._held:
                    continue
            self._run(key, find)

    def _due_again(self, held: _Held) -> bool:
        return (
            held.search.status is PictureSearchStatus.FAILED
            and self._monotonic() - held.at >= self._retry_after_s
        )

    def _run(self, key: str, find: Callable[[], Sequence[ImageOption]]) -> None:
        try:
            done = PictureSearch(PictureSearchStatus.READY, tuple(find()))
        except ImageSearchError as e:
            logger.warning("picture search %r failed: %s", key, e)
            done = PictureSearch(PictureSearchStatus.FAILED)
        except Exception:
            # Any other error still ends the search: left SEARCHING it would never be asked again.
            logger.exception("picture search %r broke", key)
            done = PictureSearch(PictureSearchStatus.FAILED)
        with self._changed:
            if key in self._held:
                self._held[key] = _Held(done, self._monotonic())
