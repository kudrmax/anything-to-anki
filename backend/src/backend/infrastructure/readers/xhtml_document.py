"""Turns blocks read from (X)HTML into a document."""

from __future__ import annotations

from typing import TYPE_CHECKING

from backend.domain.value_objects.document import (
    Block,
    Document,
    Heading,
    Line,
    ListItem,
    Paragraph,
    ParagraphMode,
)
from backend.infrastructure.epub.models import BlockRole

if TYPE_CHECKING:
    from collections.abc import Sequence

    from backend.infrastructure.epub.models import TextBlock

HEADING_LINE_SEPARATOR = " "


def xhtml_document(blocks: Sequence[TextBlock], *, song: bool = False) -> Document:
    """A paragraph, heading or list item keeps the lines its `<br>`s make.

    A song is all lines: every element is a stanza.
    """
    return Document(blocks=tuple(_block(unit, song=song) for unit in _units(blocks)))


def _units(blocks: Sequence[TextBlock]) -> list[list[TextBlock]]:
    units: list[list[TextBlock]] = []
    for block in blocks:
        if block.continues and units and units[-1][0].role is block.role:
            units[-1].append(block)
        else:
            units.append([block])
    return units


def _block(unit: list[TextBlock], *, song: bool) -> Block:
    first = unit[0]
    lines = tuple(Line(block.text) for block in unit)
    if song:
        return Paragraph(lines=lines, mode=ParagraphMode.LINES)
    match first.role:
        case BlockRole.HEADING:
            text = HEADING_LINE_SEPARATOR.join(block.text for block in unit)
            return Heading(level=first.heading_level, text=text)
        case BlockRole.LIST_ITEM:
            return ListItem(lines=lines, ordered=first.ordered, depth=first.list_depth)
        case BlockRole.PARAGRAPH:
            return Paragraph(lines=lines, mode=ParagraphMode.FLOW)
