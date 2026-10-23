from __future__ import annotations

import logging
import time
from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from threading import Lock
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
    """Picture searches on a few threads of their own, remembered for the app's life."""

    def __init__(
        self,
        workers: int = PICTURE_SEARCH_WORKERS,
        kept: int = KEPT_PICTURE_SEARCHES,
        retry_after_s: float = FAILED_PICTURE_SEARCH_RETRY_S,
        monotonic: Callable[[], float] = time.monotonic,
    ) -> None:
        self._pool = ThreadPoolExecutor(max_workers=workers, thread_name_prefix="picture-search")
        self._kept = kept
        self._retry_after_s = retry_after_s
        self._monotonic = monotonic
        self._lock = Lock()
        self._held: OrderedDict[str, _Held] = OrderedDict()

    def search(self, key: str, find: Callable[[], Sequence[ImageOption]]) -> PictureSearch:
        with self._lock:
            held = self._held.get(key)
            if held is not None and not self._due_again(held):
                self._held.move_to_end(key)
                return held.search
            self._held[key] = _Held(_SEARCHING, self._monotonic())
            self._held.move_to_end(key)
            while len(self._held) > self._kept:
                self._held.popitem(last=False)
        self._pool.submit(self._run, key, find)
        return _SEARCHING

    def close(self) -> None:
        """Searches not started are dropped; running ones finish on their own."""
        self._pool.shutdown(wait=False, cancel_futures=True)

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
        with self._lock:
            if key in self._held:
                self._held[key] = _Held(done, self._monotonic())
