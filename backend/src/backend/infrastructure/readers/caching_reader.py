from __future__ import annotations

import os
import threading
import time
from collections import OrderedDict
from typing import TYPE_CHECKING

from backend.domain.ports.format_reader import FormatReader
from backend.domain.value_objects.source_input import LocalFile

if TYPE_CHECKING:
    from collections.abc import Callable

    from backend.domain.value_objects.content import Content
    from backend.domain.value_objects.format import Format
    from backend.domain.value_objects.question import Answers, Question
    from backend.domain.value_objects.source_input import SourceInput

# Adding asks questions over several calls, each reading every input again; a read is kept
# for one add, not longer.
CACHE_TTL_SECONDS = 10 * 60
CACHE_MAX_ENTRIES = 32

type _FileVersion = tuple[int, int] | None
type _Key = tuple[object, ...]


class CachingFormatReader(FormatReader):
    """Keeps what a reader read for a while, so the calls of one add read each input once.

    A file changed on disk is read again.
    """

    def __init__(
        self, inner: FormatReader, clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._inner = inner
        self._clock = clock
        self._entries: OrderedDict[_Key, tuple[float, object]] = OrderedDict()
        self._lock = threading.Lock()

    @property
    def format(self) -> Format:
        return self._inner.format

    def questions(self, source_input: SourceInput) -> tuple[Question, ...]:
        key = ("questions", source_input, _version(source_input))
        cached = self._get(key)
        if cached is not None:
            return cached  # type: ignore[return-value]  # stored by this method only
        asked = self._inner.questions(source_input)
        self._put(key, asked)
        return asked

    def read(self, source_input: SourceInput, answers: Answers) -> Content:
        own = {question.id for question in self.questions(source_input)}
        given = tuple(sorted((k, v) for k, v in answers.chosen.items() if k in own))
        key = ("read", source_input, _version(source_input), given)
        cached = self._get(key)
        if cached is not None:
            return cached  # type: ignore[return-value]  # stored by this method only
        content = self._inner.read(source_input, answers)
        self._put(key, content)
        return content

    def _get(self, key: _Key) -> object | None:
        with self._lock:
            entry = self._entries.get(key)
            if entry is None:
                return None
            stored_at, value = entry
            if self._clock() - stored_at > CACHE_TTL_SECONDS:
                del self._entries[key]
                return None
            self._entries.move_to_end(key)
            return value

    def _put(self, key: _Key, value: object) -> None:
        with self._lock:
            self._entries[key] = (self._clock(), value)
            self._entries.move_to_end(key)
            while len(self._entries) > CACHE_MAX_ENTRIES:
                self._entries.popitem(last=False)


def _version(source_input: SourceInput) -> tuple[_FileVersion, ...]:
    if not isinstance(source_input, LocalFile):
        return ()
    paths = [source_input.path, source_input.subtitles_path]
    return tuple(_file_version(path) for path in paths if path)


def _file_version(path: str) -> _FileVersion:
    try:
        stat = os.stat(os.path.expanduser(path))
    except OSError:
        return None
    return (stat.st_mtime_ns, stat.st_size)
