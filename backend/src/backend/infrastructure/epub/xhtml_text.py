from __future__ import annotations

import re
from dataclasses import dataclass, field
from html.parser import HTMLParser

from backend.infrastructure.epub.models import BlockRole, DocumentText, TextBlock

BLOCK_TAGS: frozenset[str] = frozenset(
    {
        "address",
        "article",
        "aside",
        "blockquote",
        "body",
        "caption",
        "center",
        "dd",
        "div",
        "dl",
        "dt",
        "figcaption",
        "figure",
        "footer",
        "h1",
        "h2",
        "h3",
        "h4",
        "h5",
        "h6",
        "header",
        "hr",
        "li",
        "main",
        "ol",
        "p",
        "pre",
        "section",
        "table",
        "td",
        "th",
        "tr",
        "ul",
    }
)
LINE_BREAK_TAGS: frozenset[str] = frozenset({"br"})
VOID_TAGS: frozenset[str] = frozenset(
    {
        "area",
        "base",
        "br",
        "col",
        "embed",
        "hr",
        "img",
        "input",
        "link",
        "meta",
        "param",
        "source",
        "track",
        "wbr",
    }
)
SKIPPED_TAGS: frozenset[str] = frozenset(
    {
        "head",
        "math",
        "nav",
        "noscript",
        "rp",
        "rt",
        "script",
        "style",
        "svg",
        "template",
        "title",
    }
)
HEADING_TAGS: frozenset[str] = frozenset({"h1", "h2", "h3", "h4", "h5", "h6"})
LIST_TAGS: frozenset[str] = frozenset({"ol", "ul"})
ORDERED_LIST_TAG = "ol"
LIST_ITEM_TAG = "li"
DOCUMENT_TYPE_TAGS: frozenset[str] = frozenset({"article", "body", "div", "section"})
# Footnote markers and the notes themselves interrupt the prose, so they never reach the text.
SKIPPED_SEMANTIC_TYPES: frozenset[str] = frozenset(
    {
        "endnote",
        "endnotes",
        "footnote",
        "footnotes",
        "landmarks",
        "noteref",
        "pagebreak",
        "rearnote",
        "rearnotes",
        "toc",
    }
)
MARKER_TAGS: frozenset[str] = frozenset({"sup"})

_SEMANTIC_ATTRS: tuple[str, ...] = ("epub:type", "role")
_ROLE_PREFIX = "doc-"
_HIDDEN_STYLE_RE = re.compile(r"display\s*:\s*none", re.IGNORECASE)
_MARKER_TEXT_RE = re.compile(r"^\s*[\[(]?\s*(?:\d{1,4}|[*†‡§¶#↩↑]+)\s*[\])]?\s*$")
_INVISIBLE_RE = re.compile("[­​‌‍⁠﻿]")
_WHITESPACE_RE = re.compile(r"\s+")


def semantic_types(attrs: dict[str, str]) -> set[str]:
    """epub:type and ARIA role values, with role's `doc-` prefix dropped."""
    types: set[str] = set()
    for name in _SEMANTIC_ATTRS:
        for value in attrs.get(name, "").split():
            lowered = value.lower()
            types.add(lowered.removeprefix(_ROLE_PREFIX) if name == "role" else lowered)
    return types


def normalized(text: str) -> str:
    return _WHITESPACE_RE.sub(" ", _INVISIBLE_RE.sub("", text)).strip()


@dataclass(frozen=True)
class _BlockShape:
    role: BlockRole = BlockRole.PARAGRAPH
    heading_level: int = 0
    list_depth: int = 0
    ordered: bool = False


@dataclass
class _Piece:
    text: str
    linked: bool


@dataclass
class _OpenElement:
    tag: str
    skipped: bool = False
    link: bool = False
    marker: bool = False
    heading: bool = False
    buffer: list[_Piece] = field(default_factory=list)


class _XhtmlTextParser(HTMLParser):
    """Collects paragraphs from any XHTML, closing whatever the markup leaves open."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._stack: list[_OpenElement] = []
        self._blocks: list[TextBlock] = []
        self._pieces: list[_Piece] = []
        self._anchors: dict[str, int] = {}
        self._types: set[str] = set()
        self._first_heading: str | None = None
        self._heading_pieces: list[str] = []
        self._skip_depth = 0
        self._link_depth = 0
        self._heading_depth = 0
        self._continues = False

    def result(self) -> DocumentText:
        self.close()
        shape = self._shape()
        while self._stack:
            self._close_element(self._stack.pop())
        self._flush(shape)
        return DocumentText(
            blocks=tuple(self._blocks),
            anchors=self._anchors,
            semantic_types=frozenset(self._types),
            first_heading=self._first_heading,
        )

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = {name.lower(): value or "" for name, value in attrs}
        if tag in BLOCK_TAGS:
            self._flush(self._shape())
        elif tag in LINE_BREAK_TAGS:
            self._flush(self._shape(), line_break=True)
        if self._skip_depth == 0:
            self._remember_anchor(tag, values)
        types = semantic_types(values)
        if tag in DOCUMENT_TYPE_TAGS and not self._blocks and not self._pieces:
            self._types |= types
        if tag in VOID_TAGS:
            return
        element = _OpenElement(
            tag=tag,
            skipped=self._is_skipped(tag, values, types),
            link=tag == "a" and "href" in values,
            marker=tag in MARKER_TAGS or (tag == "a" and "#" in values.get("href", "")),
            heading=tag in HEADING_TAGS,
        )
        self._open_element(element)

    def handle_endtag(self, tag: str) -> None:
        # The text before the closing tag belongs to the element being closed.
        shape = self._shape()
        for depth in range(len(self._stack) - 1, -1, -1):
            if self._stack[depth].tag == tag:
                while len(self._stack) > depth:
                    self._close_element(self._stack.pop())
                break
        if tag in BLOCK_TAGS:
            self._flush(shape)

    def handle_data(self, data: str) -> None:
        if self._skip_depth > 0 or not data:
            return
        piece = _Piece(text=data, linked=self._link_depth > 0)
        marker = self._innermost_marker()
        if marker is not None:
            marker.buffer.append(piece)
        else:
            self._pieces.append(piece)
        if self._heading_depth > 0:
            self._heading_pieces.append(data)

    def _is_skipped(self, tag: str, values: dict[str, str], types: set[str]) -> bool:
        return (
            tag in SKIPPED_TAGS
            or bool(types & SKIPPED_SEMANTIC_TYPES)
            or "hidden" in values
            or bool(_HIDDEN_STYLE_RE.search(values.get("style", "")))
        )

    def _remember_anchor(self, tag: str, values: dict[str, str]) -> None:
        for name in ("id", "name") if tag == "a" else ("id",):
            anchor = values.get(name)
            if anchor:
                self._anchors.setdefault(anchor, len(self._blocks))

    def _open_element(self, element: _OpenElement) -> None:
        self._stack.append(element)
        self._skip_depth += element.skipped
        self._link_depth += element.link
        self._heading_depth += element.heading

    def _close_element(self, element: _OpenElement) -> None:
        self._skip_depth -= element.skipped
        self._link_depth -= element.link
        self._heading_depth -= element.heading
        if element.marker:
            self._release_marker(element)
        if element.heading and self._heading_depth == 0:
            heading = normalized("".join(self._heading_pieces))
            self._heading_pieces = []
            if heading and self._first_heading is None:
                self._first_heading = heading

    def _release_marker(self, element: _OpenElement) -> None:
        text = "".join(piece.text for piece in element.buffer)
        if _MARKER_TEXT_RE.match(text):
            return
        outer = self._innermost_marker()
        (outer.buffer if outer is not None else self._pieces).extend(element.buffer)

    def _innermost_marker(self) -> _OpenElement | None:
        for element in reversed(self._stack):
            if element.marker:
                return element
        return None

    def _shape(self) -> _BlockShape:
        tags = [element.tag for element in self._stack]
        for tag in reversed(tags):
            if tag in HEADING_TAGS:
                return _BlockShape(role=BlockRole.HEADING, heading_level=int(tag[1]))
        if LIST_ITEM_TAG not in tags:
            return _BlockShape()
        lists = [tag for tag in tags if tag in LIST_TAGS]
        return _BlockShape(
            role=BlockRole.LIST_ITEM,
            list_depth=max(len(lists) - 1, 0),
            ordered=bool(lists) and lists[-1] == ORDERED_LIST_TAG,
        )

    def _flush(self, shape: _BlockShape, *, line_break: bool = False) -> None:
        emitted = False
        if self._pieces:
            text = normalized("".join(piece.text for piece in self._pieces))
            link_text = normalized("".join(piece.text for piece in self._pieces if piece.linked))
            self._pieces = []
            if text:
                self._blocks.append(
                    TextBlock(
                        text=text,
                        link_chars=len(link_text),
                        role=shape.role,
                        heading_level=shape.heading_level,
                        list_depth=shape.list_depth,
                        ordered=shape.ordered,
                        continues=self._continues,
                    )
                )
                emitted = True
        # A line after <br> goes on the paragraph, unless nothing came before it.
        self._continues = (self._continues or emitted) if line_break else False


class XhtmlTextExtractor:
    """Turns one XHTML document of a book into paragraphs of plain text."""

    def extract(self, markup: str) -> DocumentText:
        parser = _XhtmlTextParser()
        parser.feed(markup)
        return parser.result()
