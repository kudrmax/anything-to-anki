"""ThrottledHttpFileDownloader paces requests and waits out HTTP 429."""
from __future__ import annotations

import urllib.error
from email.message import Message
from typing import TYPE_CHECKING

import pytest
from backend.infrastructure.adapters.throttled_http_file_downloader import (
    ThrottledHttpFileDownloader,
)

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = pytest.mark.unit

URL = "https://example.com/audio.mp3"
MIN_INTERVAL_S = 1.0
RETRY_DELAYS_S = (5.0, 15.0)


def _http_error(code: int, retry_after: str | None = None) -> urllib.error.HTTPError:
    headers = Message()
    if retry_after is not None:
        headers["Retry-After"] = retry_after
    return urllib.error.HTTPError(URL, code, "error", headers, None)


class _FakeTime:
    """A clock that only moves when the downloader sleeps."""

    def __init__(self) -> None:
        self.now = 100.0
        self.sleeps: list[float] = []

    def clock(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.now += seconds


class _FakeFetch:
    """Returns queued results in order; an exception in the queue is raised."""

    def __init__(self, *results: bytes | Exception) -> None:
        self._results = list(results)
        self.calls = 0

    def __call__(self, url: str) -> bytes:
        self.calls += 1
        result = self._results.pop(0)
        if isinstance(result, Exception):
            raise result
        return result


def _downloader(fetch: _FakeFetch, time: _FakeTime) -> ThrottledHttpFileDownloader:
    return ThrottledHttpFileDownloader(
        min_interval_s=MIN_INTERVAL_S,
        retry_delays_s=RETRY_DELAYS_S,
        fetch=fetch,
        sleep=time.sleep,
        clock=time.clock,
    )


def test_writes_downloaded_bytes(tmp_path: Path) -> None:
    dest = tmp_path / "a.mp3"

    _downloader(_FakeFetch(b"audio"), _FakeTime()).download(URL, str(dest))

    assert dest.read_bytes() == b"audio"


def test_consecutive_downloads_are_spaced_out(tmp_path: Path) -> None:
    time = _FakeTime()
    downloader = _downloader(_FakeFetch(b"a", b"b"), time)

    downloader.download(URL, str(tmp_path / "a.mp3"))
    downloader.download(URL, str(tmp_path / "b.mp3"))

    assert time.sleeps == [MIN_INTERVAL_S]


def test_waits_and_retries_when_rate_limited(tmp_path: Path) -> None:
    time = _FakeTime()
    fetch = _FakeFetch(_http_error(429), b"audio")
    dest = tmp_path / "a.mp3"

    _downloader(fetch, time).download(URL, str(dest))

    assert dest.read_bytes() == b"audio"
    assert fetch.calls == 2
    assert time.sleeps == [RETRY_DELAYS_S[0]]


def test_server_retry_after_overrides_default_delay(tmp_path: Path) -> None:
    time = _FakeTime()
    fetch = _FakeFetch(_http_error(429, retry_after="42"), b"audio")

    _downloader(fetch, time).download(URL, str(tmp_path / "a.mp3"))

    assert time.sleeps == [42.0]


def test_gives_up_after_all_retries_and_leaves_no_file(tmp_path: Path) -> None:
    fetch = _FakeFetch(_http_error(429), _http_error(429), _http_error(429))
    dest = tmp_path / "a.mp3"

    with pytest.raises(urllib.error.HTTPError):
        _downloader(fetch, _FakeTime()).download(URL, str(dest))

    assert fetch.calls == len(RETRY_DELAYS_S) + 1
    assert not dest.exists()


def test_other_http_errors_are_not_retried(tmp_path: Path) -> None:
    fetch = _FakeFetch(_http_error(404), b"audio")

    with pytest.raises(urllib.error.HTTPError):
        _downloader(fetch, _FakeTime()).download(URL, str(tmp_path / "a.mp3"))

    assert fetch.calls == 1
