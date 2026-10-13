from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class EpubChapter:
    """A chapter of readable prose: paragraphs separated by blank lines."""

    title: str | None
    text: str
    word_count: int


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
class TextBlock:
    """One paragraph-like piece of a document's text."""

    text: str
    link_chars: int


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
