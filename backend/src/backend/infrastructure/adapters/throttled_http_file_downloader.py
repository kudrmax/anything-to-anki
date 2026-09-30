from __future__ import annotations

import logging
import os
import time
import urllib.error
import urllib.request
from typing import TYPE_CHECKING

from backend.domain.ports.file_downloader import FileDownloader

if TYPE_CHECKING:
    from collections.abc import Callable

logger = logging.getLogger(__name__)

HTTP_TOO_MANY_REQUESTS = 429
RETRY_AFTER_HEADER = "Retry-After"
DEFAULT_MIN_INTERVAL_S = 1.0
DEFAULT_RETRY_DELAYS_S: tuple[float, ...] = (30.0, 60.0, 120.0)
_USER_AGENT = "Mozilla/5.0"
_REQUEST_TIMEOUT_S = 30
_INCOMPLETE_SUFFIX = ".part"


def _http_get(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT})  # noqa: S310
    with urllib.request.urlopen(req, timeout=_REQUEST_TIMEOUT_S) as resp:  # noqa: S310
        body: bytes = resp.read()
    return body


class ThrottledHttpFileDownloader(FileDownloader):
    """Downloads files over HTTP without hammering the host.

    Requests are spaced at least ``min_interval_s`` apart, and an HTTP 429 is
    waited out — for as long as the server asks via Retry-After, otherwise for
    the next of ``retry_delays_s`` — before trying again. Bulk downloads from a
    dictionary site get rate-limited otherwise.

    One instance must be shared by all downloads for the pacing to work.
    """

    def __init__(
        self,
        min_interval_s: float = DEFAULT_MIN_INTERVAL_S,
        retry_delays_s: tuple[float, ...] = DEFAULT_RETRY_DELAYS_S,
        fetch: Callable[[str], bytes] = _http_get,
        sleep: Callable[[float], None] = time.sleep,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._min_interval_s = min_interval_s
        self._retry_delays_s = retry_delays_s
        self._fetch = fetch
        self._sleep = sleep
        self._clock = clock
        self._last_request_at: float | None = None

    def download(self, url: str, dest: str) -> None:
        body = self._fetch_with_retries(url)
        incomplete = f"{dest}{_INCOMPLETE_SUFFIX}"
        with open(incomplete, "wb") as out:
            out.write(body)
        os.replace(incomplete, dest)

    def _fetch_with_retries(self, url: str) -> bytes:
        for delay in self._retry_delays_s:
            try:
                return self._paced_fetch(url)
            except urllib.error.HTTPError as exc:
                if exc.code != HTTP_TOO_MANY_REQUESTS:
                    raise
                wait_s = self._retry_after_s(exc) or delay
                logger.warning("rate limited by %s, waiting %.0fs", url, wait_s)
                self._sleep(wait_s)
        return self._paced_fetch(url)

    def _paced_fetch(self, url: str) -> bytes:
        if self._last_request_at is not None:
            remaining = self._min_interval_s - (self._clock() - self._last_request_at)
            if remaining > 0:
                self._sleep(remaining)
        try:
            return self._fetch(url)
        finally:
            self._last_request_at = self._clock()

    @staticmethod
    def _retry_after_s(exc: urllib.error.HTTPError) -> float | None:
        raw = exc.headers.get(RETRY_AFTER_HEADER) if exc.headers else None
        if raw is None or not raw.isdigit():
            return None
        return float(raw)
