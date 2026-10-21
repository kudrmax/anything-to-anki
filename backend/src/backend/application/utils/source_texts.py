from __future__ import annotations

import threading
from collections import OrderedDict
from dataclasses import dataclass
from typing import TYPE_CHECKING

from backend.domain.services.document_layout import DocumentLayout
from backend.domain.services.text_chunks import block_bounds, list_numbers, text_chunks

if TYPE_CHECKING:
    from collections.abc import Callable

    from backend.domain.services.text_chunks import TextChunk
    from backend.domain.value_objects.document import Document

# The most characters of text the kept sources hold together: about four books, each one
# source. The source read last stays even when it alone is longer.
SOURCE_TEXTS_CHARS = 10_000_000


@dataclass(frozen=True)
class SourceText:
    """A source's document laid out for reading in chunks: its text, its chunks, where each
    block stands in the text and the number of each list item."""

    layout: DocumentLayout
    chunks: tuple[TextChunk, ...]
    bounds: tuple[tuple[int, int], ...]
    numbers: tuple[int | None, ...]

    @staticmethod
    def of(document: Document) -> SourceText:
        return SourceText(
            layout=DocumentLayout(document),
            chunks=text_chunks(document),
            bounds=block_bounds(document),
            numbers=list_numbers(document.blocks),
        )


class SourceTexts:
    """The laid-out documents of the sources read last, kept for the life of the process.
    Each is kept under its source with the fingerprint of the stored document it was laid
    out from; a source whose stored document has another fingerprint (its id given to a new
    source) is laid out anew. Safe to share between threads."""

    def __init__(self, max_chars: int = SOURCE_TEXTS_CHARS) -> None:
        self._max_chars = max_chars
        self._kept: OrderedDict[int, tuple[str, SourceText]] = OrderedDict()
        self._chars = 0
        self._lock = threading.Lock()

    def of(
        self, source_id: int, fingerprint: str, read: Callable[[], Document],
    ) -> SourceText:
        """The source's text, laid out from `read()` unless it is kept with this
        fingerprint."""
        with self._lock:
            kept = self._kept.get(source_id)
            if kept is not None and kept[0] == fingerprint:
                self._kept.move_to_end(source_id)
                return kept[1]
        text = SourceText.of(read())
        with self._lock:
            self._drop(source_id)
            self._kept[source_id] = (fingerprint, text)
            self._chars += len(text.layout.text)
            while self._chars > self._max_chars and len(self._kept) > 1:
                self._drop(next(iter(self._kept)))
        return text

    def _drop(self, source_id: int) -> None:
        kept = self._kept.pop(source_id, None)
        if kept is not None:
            self._chars -= len(kept[1].layout.text)
