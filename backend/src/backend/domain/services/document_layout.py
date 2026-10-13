from __future__ import annotations

import bisect
from dataclasses import dataclass

from backend.domain.exceptions import InvalidPhraseError
from backend.domain.value_objects.document import (
    BLOCK_SEPARATOR,
    FLOW_LINE_SEPARATOR,
    LINES_LINE_SEPARATOR,
    Block,
    Document,
    Heading,
    Line,
    ListItem,
    Paragraph,
    ParagraphMode,
)
from backend.domain.value_objects.document_position import DocumentPosition

ONE_BLOCK_MESSAGE = "A phrase must stay within one paragraph"
EMPTY_SELECTION_MESSAGE = "Select some text"


@dataclass(frozen=True)
class _PlacedLine:
    block: int
    line: int
    start: int
    end: int


class DocumentLayout:
    """The document as one plain text (see Document.text), and the way back from the
    text's offsets to places in the document."""

    def __init__(self, document: Document) -> None:
        self._document = document
        placed: list[_PlacedLine] = []
        parts: list[str] = []
        offset = 0
        for block_index, block in enumerate(document.blocks):
            if block_index:
                parts.append(BLOCK_SEPARATOR)
                offset += len(BLOCK_SEPARATOR)
            texts, separator = _line_texts(block)
            for line_index, text in enumerate(texts):
                if line_index:
                    parts.append(separator)
                    offset += len(separator)
                placed.append(_PlacedLine(block_index, line_index, offset, offset + len(text)))
                parts.append(text)
                offset += len(text)
        self._lines = tuple(placed)
        self._starts = [line.start for line in placed]
        self._by_place = {(line.block, line.line): line for line in placed}
        self.text = "".join(parts)

    @property
    def document(self) -> Document:
        return self._document

    def position(self, start: int, end: int) -> DocumentPosition:
        """The place of the text between two offsets; both lie in one block."""
        first = self._line_at(start)
        last = self._line_at(max(end - 1, start))
        if first.block != last.block:
            msg = f"Text {start}..{end} runs across blocks {first.block} and {last.block}"
            raise ValueError(msg)
        return DocumentPosition(
            block=first.block,
            start_line=first.line,
            start_char=start - first.start,
            end_line=last.line,
            end_char=end - last.start,
        )

    def span(self, position: DocumentPosition) -> tuple[int, int]:
        """Offsets of a position in the text."""
        return (
            self._placed(position.block, position.start_line).start + position.start_char,
            self._placed(position.block, position.end_line).start + position.end_char,
        )

    def selected(
        self, start: tuple[int, int, int], end: tuple[int, int, int],
    ) -> DocumentPosition:
        """What the user selected, from (block, line, char) to (block, line, char), without
        the whitespace at its edges. A selection stays within one block."""
        if start[0] != end[0]:
            raise InvalidPhraseError(ONE_BLOCK_MESSAGE)
        first = self.line_offset(start[0], start[1]) + start[2]
        last = self.line_offset(end[0], end[1]) + end[2]
        while first < last and self.text[first].isspace():
            first += 1
        while last > first and self.text[last - 1].isspace():
            last -= 1
        if first >= last:
            raise InvalidPhraseError(EMPTY_SELECTION_MESSAGE)
        return self.position(first, last)

    def line_offset(self, block: int, line: int) -> int:
        """Where a line starts in the text."""
        return self._placed(block, line).start

    def fragment(self, position: DocumentPosition) -> str:
        start, end = self.span(position)
        return self.text[start:end]

    def lines(self, position: DocumentPosition) -> tuple[Line, ...]:
        """The lines a position takes; a heading has none."""
        block = self._document.blocks[position.block]
        if isinstance(block, Heading):
            return ()
        return block.lines[position.start_line : position.end_line + 1]

    def _line_at(self, offset: int) -> _PlacedLine:
        index = bisect.bisect_right(self._starts, offset) - 1
        if index < 0:
            msg = f"Offset {offset} is before the text"
            raise ValueError(msg)
        return self._lines[index]

    def _placed(self, block: int, line: int) -> _PlacedLine:
        placed = self._by_place.get((block, line))
        if placed is None:
            msg = f"No line {line} in block {block}"
            raise ValueError(msg)
        return placed


def _line_texts(block: Block) -> tuple[list[str], str]:
    match block:
        case Heading():
            return [block.text], FLOW_LINE_SEPARATOR
        case Paragraph(mode=ParagraphMode.LINES):
            return [line.text for line in block.lines], LINES_LINE_SEPARATOR
        case Paragraph() | ListItem():
            return [line.text for line in block.lines], FLOW_LINE_SEPARATOR
