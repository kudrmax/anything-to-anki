from __future__ import annotations

from typing import TYPE_CHECKING

from backend.domain.value_objects.document import Heading

if TYPE_CHECKING:
    from backend.domain.value_objects.document import Document
    from backend.domain.value_objects.document_position import DocumentPosition


def time_of(document: Document, position: DocumentPosition) -> tuple[int, int] | None:
    """From the start of the first line a piece takes to the end of the last, if they are timed."""
    block = document.blocks[position.block]
    if isinstance(block, Heading):
        return None
    lines = block.lines[position.start_line : position.end_line + 1]
    starts = [line.start_ms for line in lines]
    ends = [line.end_ms for line in lines]
    if not lines or None in starts or None in ends:
        return None
    return min(s for s in starts if s is not None), max(e for e in ends if e is not None)
