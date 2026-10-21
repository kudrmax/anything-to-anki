from __future__ import annotations

import hashlib
import inspect
import io
import logging
import os
import pickle
import re
import shutil
import sys
import threading
from abc import ABC, abstractmethod
from contextlib import contextmanager
from dataclasses import dataclass
from typing import TYPE_CHECKING

from backend.domain.exceptions import ReviewNotFoundError
from backend.domain.ports.review_order_store import ReviewOrderStore
from backend.infrastructure.review.in_memory_review_order_store import InMemoryReviewOrderStore

if TYPE_CHECKING:
    from collections.abc import Iterator
    from pathlib import Path

logger = logging.getLogger(__name__)

# The folders of the reviews written last that stay; every tab of one user fits.
REVIEWS_ON_DISK = 64
HEAVY_FILE = "order.pickle"
LIGHT_FILE = "state.pickle"
# The ids the store gives (secrets.token_urlsafe): only such a name becomes a folder.
_REVIEW_ID = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
_APP_PACKAGE = "backend."
_DIGEST_BYTES = 16


class ReviewCodec[R](ABC):
    """How a held review is written apart: its heavy part, written again only when its mark
    moves, and the rest, written after every hold."""

    @abstractmethod
    def heavy(self, review: R) -> object: ...

    @abstractmethod
    def heavy_mark(self, review: R) -> int:
        """Moves on whenever the heavy part changes."""

    @abstractmethod
    def light(self, review: R) -> object: ...

    @abstractmethod
    def joined(self, heavy: object, light: object) -> R: ...


@dataclass(frozen=True)
class _Snapshot:
    """A pickled part of a review and the app modules its objects come from, with a digest
    of their source: a review written by other code is not read back."""

    modules: tuple[str, ...]
    digest: bytes
    payload: bytes


class FileReviewOrderStore[R](ReviewOrderStore[R]):
    """The open reviews held in memory, each also written to its own folder under `root`
    before its answer goes out: a review memory let go, by a restart or newer reviews, is
    read back from there, so the client goes on with the same order. A review whose folder
    is gone, unreadable or written by other code is not held: the client opens it again.
    The folders over REVIEWS_ON_DISK, least recently written first, go."""

    def __init__(
        self,
        root: Path,
        codec: ReviewCodec[R],
        memory: InMemoryReviewOrderStore[R] | None = None,
    ) -> None:
        self._root = root
        self._codec = codec
        self._memory = memory or InMemoryReviewOrderStore()
        self._heavy_marks: dict[str, int] = {}
        self._lock = threading.Lock()

    def open(self, review: R) -> str:
        review_id = self._memory.open(review)
        self._write(review_id, review)
        self._prune()
        return review_id

    @contextmanager
    def hold(self, review_id: str) -> Iterator[R]:
        self._read_back(review_id)
        with self._memory.hold(review_id) as review:
            try:
                yield review
            finally:
                self._write(review_id, review)

    @contextmanager
    def pin(self, review_id: str) -> Iterator[None]:
        self._read_back(review_id)
        with self._memory.pin(review_id):
            yield

    def _read_back(self, review_id: str) -> None:
        """The review from its folder into memory, when memory let it go."""
        if self._memory.holds(review_id):
            return
        with self._lock:
            if self._memory.holds(review_id):
                return
            folder = self._folder(review_id)
            heavy = _read(folder / HEAVY_FILE)
            light = _read(folder / LIGHT_FILE)
            if heavy is None or light is None:
                raise ReviewNotFoundError(review_id)
            try:
                review = self._codec.joined(heavy, light)
            except Exception as e:
                logger.warning("An open review could not be put together: %s", review_id)
                raise ReviewNotFoundError(review_id) from e
            self._memory.keep(review_id, review)
            self._heavy_marks[review_id] = self._codec.heavy_mark(review)

    def _write(self, review_id: str, review: R) -> None:
        folder = self._folder(review_id)
        folder.mkdir(parents=True, exist_ok=True)
        mark = self._codec.heavy_mark(review)
        if self._heavy_marks.get(review_id) != mark or not (folder / HEAVY_FILE).exists():
            _write(folder / HEAVY_FILE, self._codec.heavy(review))
            self._heavy_marks[review_id] = mark
        _write(folder / LIGHT_FILE, self._codec.light(review))

    def _folder(self, review_id: str) -> Path:
        if not _REVIEW_ID.match(review_id):
            raise ReviewNotFoundError(review_id)
        return self._root / review_id

    def _prune(self) -> None:
        folders = [f for f in self._root.iterdir() if (f / LIGHT_FILE).exists()]
        folders.sort(key=lambda f: (f / LIGHT_FILE).stat().st_mtime, reverse=True)
        for folder in folders[REVIEWS_ON_DISK:]:
            self._heavy_marks.pop(folder.name, None)
            shutil.rmtree(folder, ignore_errors=True)


class _RecordingPickler(pickle.Pickler):
    """Pickles as usual and notes the app modules of the objects it meets."""

    def __init__(self, file: io.BytesIO) -> None:
        super().__init__(file, protocol=pickle.HIGHEST_PROTOCOL)
        self.modules: set[str] = set()

    # typeshed leaves NotImplemented, the documented answer "pickle it as usual", out of
    # the return type.
    def reducer_override(self, obj: object) -> object:  # type: ignore[override]
        module = type(obj).__module__ if not isinstance(obj, type) else obj.__module__
        if module.startswith(_APP_PACKAGE):
            self.modules.add(module)
        return NotImplemented


_sources: dict[str, bytes] = {}


def _digest(modules: tuple[str, ...]) -> bytes | None:
    """A digest of the modules' source as this code has it; None when one is not loaded."""
    hashed = hashlib.blake2b(digest_size=_DIGEST_BYTES)
    for name in modules:
        source = _sources.get(name)
        if source is None:
            module = sys.modules.get(name)
            if module is None:
                return None
            source = _sources[name] = inspect.getsource(module).encode()
        hashed.update(name.encode() + b"\0" + source + b"\0")
    return hashed.digest()


def _write(path: Path, part: object) -> None:
    """The part, written whole or not at all: a new file takes the old one's place."""
    buffer = io.BytesIO()
    pickler = _RecordingPickler(buffer)
    pickler.dump(part)
    modules = tuple(sorted(pickler.modules))
    snapshot = _Snapshot(modules, _digest(modules) or b"", buffer.getvalue())
    draft = path.with_suffix(".draft")
    draft.write_bytes(pickle.dumps(snapshot, protocol=pickle.HIGHEST_PROTOCOL))
    os.replace(draft, path)


def _read(path: Path) -> object | None:
    # The files are the app's own, written by _write into its data folder.
    try:
        snapshot = pickle.loads(path.read_bytes())  # noqa: S301
        if not isinstance(snapshot, _Snapshot) or _digest(snapshot.modules) != snapshot.digest:
            return None
        part: object = pickle.loads(snapshot.payload)  # noqa: S301
        return part
    except FileNotFoundError:
        return None
    except Exception:
        logger.warning("An open review could not be read back from %s", path, exc_info=True)
        return None
