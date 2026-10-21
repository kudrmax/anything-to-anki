from __future__ import annotations

import threading
from collections import OrderedDict
from dataclasses import dataclass
from typing import TYPE_CHECKING

from backend.domain.services.document_layout import DocumentLayout
from backend.domain.services.text_chunks import block_bounds, list_numbers, text_chunks
from backend.domain.value_objects.document import Heading

if TYPE_CHECKING:
    from collections.abc import Callable

    from backend.domain.services.text_chunks import TextChunk
    from backend.domain.value_objects.document import Document

# The most memory the kept sources take together, as SourceText.size estimates it: about
# four books of prose, each one source. The source read last stays even when it alone
# takes more.
SOURCE_TEXTS_BYTES = 200_000_000
# What a laid-out document takes per character and per line, its document included: an
# upper bound of what tracemalloc measured on prose (5.9–7.7 bytes per character), lyrics,
# subtitles and headings (33–45 bytes per character, most of it per line).
LAID_OUT_BYTES_PER_CHAR = 6
LAID_OUT_BYTES_PER_LINE = 700


@dataclass(frozen=True)
class SourceText:
    """A source's document laid out for reading in chunks: its text, its chunks, where each
    block stands in the text and the number of each list item."""

    layout: DocumentLayout
    chunks: tuple[TextChunk, ...]
    bounds: tuple[tuple[int, int], ...]
    numbers: tuple[int | None, ...]

    @property
    def size(self) -> int:
        """An upper estimate of the memory it takes, in bytes."""
        lines = sum(
            1 if isinstance(block, Heading) else len(block.lines)
            for block in self.layout.document.blocks
        )
        return (
            len(self.layout.text) * LAID_OUT_BYTES_PER_CHAR + lines * LAID_OUT_BYTES_PER_LINE
        )

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
    source) is laid out anew. Bounded by the memory they take. Safe to share between
    threads."""

    def __init__(self, max_bytes: int = SOURCE_TEXTS_BYTES) -> None:
        self._max_bytes = max_bytes
        self._kept: OrderedDict[int, tuple[str, SourceText, int]] = OrderedDict()
        self._bytes = 0
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
        size = text.size
        with self._lock:
            self._drop(source_id)
            self._kept[source_id] = (fingerprint, text, size)
            self._bytes += size
            while self._bytes > self._max_bytes and len(self._kept) > 1:
                self._drop(next(iter(self._kept)))
        return text

    def _drop(self, source_id: int) -> None:
        kept = self._kept.pop(source_id, None)
        if kept is not None:
            self._bytes -= kept[2]
