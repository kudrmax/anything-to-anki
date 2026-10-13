from __future__ import annotations

import re
from dataclasses import dataclass
from typing import TYPE_CHECKING

from backend.infrastructure.epub.models import EpubChapter
from backend.infrastructure.epub.words import count_words

if TYPE_CHECKING:
    from backend.infrastructure.epub.models import DocumentText, TextBlock, TocEntry

MIN_CHAPTER_WORDS = 100
# Copyright and title pages are short; a real chapter that mentions ISBN is long enough to keep.
FRONT_MATTER_MAX_WORDS = 600
FRONT_MATTER_RE = re.compile(r"\bISBN\b|all rights reserved", re.IGNORECASE)
# A page of several lines that are mostly links is a table of contents, whatever its markup says.
NAVIGATION_LINK_RATIO = 0.5
NAVIGATION_MIN_BLOCKS = 3
SKIPPED_DOCUMENT_TYPES: frozenset[str] = frozenset(
    {
        "bibliography",
        "colophon",
        "copyright-page",
        "cover",
        "endnotes",
        "footnotes",
        "halftitlepage",
        "index",
        "landmarks",
        "loi",
        "lot",
        "rearnotes",
        "titlepage",
        "toc",
    }
)
SKIPPED_TITLES: frozenset[str] = frozenset(
    {
        "bibliography",
        "contents",
        "copyright",
        "copyright page",
        "cover",
        "endnotes",
        "index",
        "notes",
        "references",
        "table of contents",
        "title page",
    }
)
SKIPPED_TITLE_PREFIXES: tuple[str, ...] = ("also by", "index")
# Books converted from MOBI point the contents at the last lines before a page break;
# a chapter never starts with a few words left in its file, so it starts with the next file.
STRAY_ANCHOR_MAX_WORDS = 150
# Contents of converted books point near the chapter, not at it: the chapter starts at its title,
# looked up this many paragraphs ahead.
TITLE_SEARCH_BLOCKS = 80
_NUMBERING_RE = re.compile(r"^\s*(?:chapter\s+)?[\divxlc]+[.:)\s-]+", re.IGNORECASE)
_NON_WORD_RE = re.compile(r"\W+")
# Contents nest parts, chapters and sections; the shallowest level with no piece longer
# than a long chapter is the chapter level: parts are cut further, chapters are not.
LONG_CHAPTER_WORDS = 25000
PARAGRAPH_SEPARATOR = "\n\n"
_TITLE_PUNCTUATION = " .:"


@dataclass(frozen=True)
class _Boundary:
    position: int
    label: str | None
    depth: int
    before_contents: bool = False


@dataclass(frozen=True)
class _Layout:
    """The book's documents laid out as one run of paragraphs."""

    blocks: tuple[TextBlock, ...]
    word_offsets: tuple[int, ...]
    document_starts: dict[str, int]
    document_ends: dict[str, int]
    documents: dict[str, DocumentText]

    def words_between(self, start: int, end: int) -> int:
        return self.word_offsets[end] - self.word_offsets[start]


class ChapterAssembler:
    """Cuts the book's paragraphs into chapters along its table of contents."""

    def assemble(
        self,
        documents: list[tuple[str, DocumentText]],
        toc: list[TocEntry],
    ) -> list[EpubChapter]:
        layout = self._layout(documents)
        boundaries = self._boundaries(layout, toc)
        chapters: list[EpubChapter] = []
        for current, following in zip(boundaries, [*boundaries[1:], None], strict=True):
            end = following.position if following else len(layout.blocks)
            chapter = self._chapter(layout, current, end)
            if self._is_prose(chapter, before_contents=current.before_contents):
                chapters.append(chapter)
        return chapters

    def _is_readable(self, document: DocumentText) -> bool:
        is_navigation = (
            len(document.blocks) >= NAVIGATION_MIN_BLOCKS
            and document.link_ratio >= NAVIGATION_LINK_RATIO
        )
        return not is_navigation and not document.semantic_types & SKIPPED_DOCUMENT_TYPES

    def _layout(self, documents: list[tuple[str, DocumentText]]) -> _Layout:
        blocks: list[TextBlock] = []
        offsets: list[int] = [0]
        starts: dict[str, int] = {}
        ends: dict[str, int] = {}
        for path, document in documents:
            starts[path] = len(blocks)
            # A skipped page keeps its place: contents entries pointing at it still cut the book.
            for block in document.blocks if self._is_readable(document) else ():
                blocks.append(block)
                offsets.append(offsets[-1] + count_words(block.text))
            ends[path] = len(blocks)
        return _Layout(
            blocks=tuple(blocks),
            word_offsets=tuple(offsets),
            document_starts=starts,
            document_ends=ends,
            documents=dict(documents),
        )

    def _boundaries(self, layout: _Layout, toc: list[TocEntry]) -> list[_Boundary]:
        entries = [b for entry in toc if (b := self._resolve(layout, entry)) is not None]
        for depth in sorted({entry.depth for entry in entries}):
            chosen = self._distinct([entry for entry in entries if entry.depth <= depth], layout)
            if self._longest_words(layout, chosen) <= LONG_CHAPTER_WORDS:
                return chosen
        # Contents too sparse to cut the book into chapters: files usually hold one chapter each.
        files = [
            _Boundary(position=start, label=None, depth=0)
            for start in layout.document_starts.values()
        ]
        return self._distinct(files + entries, layout)

    def _resolve(self, layout: _Layout, entry: TocEntry) -> _Boundary | None:
        start = layout.document_starts.get(entry.document)
        if start is None:
            return None
        end = layout.document_ends[entry.document]
        anchor = layout.documents[entry.document].anchors.get(entry.fragment or "", 0)
        position = min(start + anchor, end)
        if position > start:
            titled = self._title_position(layout, position, entry.label)
            if titled is not None:
                position = titled
            elif layout.words_between(position, end) < STRAY_ANCHOR_MAX_WORDS:
                position = end
        return _Boundary(position=position, label=entry.label or None, depth=entry.depth)

    def _title_position(self, layout: _Layout, position: int, label: str) -> int | None:
        key = _title_key(label)
        if not key:
            return None
        window = layout.blocks[position : position + TITLE_SEARCH_BLOCKS]
        for offset, block in enumerate(window):
            if _title_key(block.text) == key:
                return position + offset
        return None

    def _distinct(self, boundaries: list[_Boundary], layout: _Layout) -> list[_Boundary]:
        """One boundary per position, starting with whatever precedes the contents' first entry.

        Of entries pointing to one place, the later, more specific one wins.
        """
        by_position: dict[int, _Boundary] = {
            0: _Boundary(position=0, label=None, depth=0, before_contents=True),
        }
        for boundary in boundaries:
            if boundary.position < len(layout.blocks):
                by_position[boundary.position] = boundary
        return [by_position[position] for position in sorted(by_position)]

    def _longest_words(self, layout: _Layout, boundaries: list[_Boundary]) -> int:
        ends = [b.position for b in boundaries[1:]] + [len(layout.blocks)]
        return max(
            layout.words_between(b.position, end) for b, end in zip(boundaries, ends, strict=True)
        )

    def _chapter(self, layout: _Layout, boundary: _Boundary, end: int) -> EpubChapter:
        blocks = layout.blocks[boundary.position : end]
        text = PARAGRAPH_SEPARATOR.join(block.text for block in blocks)
        return EpubChapter(
            title=boundary.label or self._heading_at(layout, boundary.position),
            text=text,
            word_count=layout.words_between(boundary.position, end),
        )

    def _heading_at(self, layout: _Layout, position: int) -> str | None:
        for path, start in layout.document_starts.items():
            if start == position and layout.documents[path].first_heading:
                return layout.documents[path].first_heading
        return None

    def _is_prose(self, chapter: EpubChapter, *, before_contents: bool) -> bool:
        """Drops front matter: title, dedication and copyright pages, contents, notes and index."""
        if chapter.word_count < MIN_CHAPTER_WORDS:
            return False
        if before_contents and chapter.word_count <= FRONT_MATTER_MAX_WORDS:
            return False
        if chapter.word_count <= FRONT_MATTER_MAX_WORDS and FRONT_MATTER_RE.search(chapter.text):
            return False
        title = (chapter.title or "").lower().strip(_TITLE_PUNCTUATION)
        return title not in SKIPPED_TITLES and not title.startswith(SKIPPED_TITLE_PREFIXES)


def _title_key(text: str) -> str:
    """A title stripped of numbering, case and punctuation, so `15. Linda` matches `LINDA`."""
    return _NON_WORD_RE.sub("", _NUMBERING_RE.sub("", text, count=1)).casefold()
