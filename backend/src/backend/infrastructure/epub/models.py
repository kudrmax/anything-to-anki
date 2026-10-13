from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

PARAGRAPH_SEPARATOR = "\n\n"


class BlockRole(StrEnum):
    PARAGRAPH = "paragraph"
    HEADING = "heading"
    LIST_ITEM = "list_item"


@dataclass(frozen=True)
class TextBlock:
    """One paragraph-like piece of a document's text.

    A line after a `<br>` is a block of its own that `continues` the one before it.
    """

    text: str
    link_chars: int
    role: BlockRole = BlockRole.PARAGRAPH
    heading_level: int = 0
    list_depth: int = 0
    ordered: bool = False
    continues: bool = False


@dataclass(frozen=True)
class EpubChapter:
    """A chapter of readable prose."""

    title: str | None
    blocks: tuple[TextBlock, ...]
    word_count: int

    @property
    def text(self) -> str:
        return PARAGRAPH_SEPARATOR.join(block.text for block in self.blocks)


@dataclass(frozen=True)
class EpubBook:
    title: str | None
    chapters: tuple[EpubChapter, ...]


@dataclass(frozen=True)
class TocEntry:
    """A table-of-contents link: a document and an optional anchor inside it."""

    label: str
    document: str
    fragment: str | None
    depth: int


@dataclass(frozen=True)
class DocumentText:
    """The readable text of one XHTML document of the book."""

    blocks: tuple[TextBlock, ...]
    anchors: dict[str, int]
    semantic_types: frozenset[str]
    first_heading: str | None

    @property
    def link_ratio(self) -> float:
        total = sum(len(block.text) for block in self.blocks)
        if total == 0:
            return 0.0
        return sum(block.link_chars for block in self.blocks) / total
