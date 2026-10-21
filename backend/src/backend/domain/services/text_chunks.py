"""A document's text in chunks of whole blocks, as the review reads it a piece at a time."""
from __future__ import annotations

import bisect
from dataclasses import dataclass
from typing import TYPE_CHECKING

from backend.domain.exceptions import TextBlockNotFoundError
from backend.domain.value_objects.document import BLOCK_SEPARATOR, ListItem, block_text

if TYPE_CHECKING:
    from collections.abc import Sequence

    from backend.domain.value_objects.document import Block, Document

# A chunk takes whole blocks while their text, blank lines between them included, is at
# most this long; a longer block is a chunk on its own.
TEXT_CHUNK_CHARS = 20_000
# The block that names the last chunk of a document.
LAST_BLOCK = -1


@dataclass(frozen=True)
class TextChunk:
    """Blocks `first_block` up to `end_block`, exclusive."""

    first_block: int
    end_block: int


def text_chunks(document: Document) -> tuple[TextChunk, ...]:
    """Consecutive chunks that together hold every block of the document, in order."""
    chunks: list[TextChunk] = []
    first = 0
    length = 0
    for index, block in enumerate(document.blocks):
        size = len(block_text(block))
        if index == first:
            length = size
        elif length + len(BLOCK_SEPARATOR) + size <= TEXT_CHUNK_CHARS:
            length += len(BLOCK_SEPARATOR) + size
        else:
            chunks.append(TextChunk(first, index))
            first, length = index, size
    if document.blocks:
        chunks.append(TextChunk(first, len(document.blocks)))
    return tuple(chunks)


def chunk_with(chunks: Sequence[TextChunk], block: int) -> TextChunk:
    """The chunk that holds the block; LAST_BLOCK names the last one."""
    if block == LAST_BLOCK and chunks:
        return chunks[-1]
    if not chunks or not 0 <= block < chunks[-1].end_block:
        raise TextBlockNotFoundError(block)
    index = bisect.bisect_right([chunk.first_block for chunk in chunks], block) - 1
    return chunks[index]


def chunk_at(
    chunks: Sequence[TextChunk], bounds: Sequence[tuple[int, int]], offset: int,
) -> TextChunk:
    """The chunk that holds the character at `offset` of the document's text (`bounds` from
    `block_bounds`). An offset between two blocks belongs to the block before it; one before
    the start or past the end, to the first or the last block."""
    if not chunks:
        raise TextBlockNotFoundError(LAST_BLOCK)
    block = bisect.bisect_right([start for start, _ in bounds], offset) - 1
    return chunk_with(chunks, min(max(block, 0), chunks[-1].end_block - 1))


def block_bounds(document: Document) -> tuple[tuple[int, int], ...]:
    """Where each block's text starts and ends in the document's text (`Document.text`)."""
    bounds: list[tuple[int, int]] = []
    offset = 0
    for block in document.blocks:
        end = offset + len(block_text(block))
        bounds.append((offset, end))
        offset = end + len(BLOCK_SEPARATOR)
    return tuple(bounds)


def list_numbers(blocks: Sequence[Block]) -> tuple[int | None, ...]:
    """The number of each list item among the items around it, None for any other block.
    Every block that is not a list item ends the list; an item counts among the items of
    its depth since the last shallower one. An unordered item has a number too."""
    counters: list[int] = []
    numbers: list[int | None] = []
    for block in blocks:
        if not isinstance(block, ListItem):
            counters.clear()
            numbers.append(None)
            continue
        depth = block.depth
        del counters[depth + 1:]
        counters.extend([0] * (depth + 1 - len(counters)))
        counters[depth] += 1
        numbers.append(counters[depth])
    return tuple(numbers)
