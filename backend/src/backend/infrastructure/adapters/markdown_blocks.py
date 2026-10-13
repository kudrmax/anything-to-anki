from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum

_FENCE_RE = re.compile(r"^\s*(```|~~~)")
_FRONT_MATTER_FENCE = "---"
_COMMENT_RE = re.compile(r"<!--.*?-->", re.DOTALL)
_HEADING_RE = re.compile(r"^\s{0,3}#{1,6}\s+(.*?)(?:\s+#+)?\s*$")
_SETEXT_UNDERLINE_RE = re.compile(r"^\s{0,3}(=+|-+)\s*$")
_SETEXT_LEVEL_ONE = "="
_RULE_RE = re.compile(r"^\s{0,3}([-*_])(\s*\1){2,}\s*$")
_QUOTE_RE = re.compile(r"^\s{0,3}(>\s?)+")
_LIST_ITEM_RE = re.compile(r"^(\s*)(?:[-*+]|(\d{1,9})[.)])\s+(?:\[[ xX]\]\s+)?")
_LIST_INDENT = 2
_TAB_WIDTH = 4
_TABLE_DELIMITER_RE = re.compile(r"^\s*\|?\s*:?-{2,}:?\s*(\|\s*:?-{2,}:?\s*)*\|?\s*$")
_TABLE_ROW_RE = re.compile(r"^\s*\|.*\|\s*$")
_LINK_DEFINITION_RE = re.compile(r"^\s{0,3}\[[^\]]+\]:\s+\S+")
_FOOTNOTE_DEFINITION_RE = re.compile(r"^\s{0,3}\[\^[^\]]+\]:\s*")

# Inline markup, applied in order: images and links before emphasis, so URLs never leak.
_INLINE_RULES: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"!\[[^\]]*\]\([^)]*\)"), ""),
    (re.compile(r"!\[[^\]]*\]\[[^\]]*\]"), ""),
    (re.compile(r"\[\^[^\]]+\]"), ""),
    (re.compile(r"\[([^\]]+)\]\([^)]*\)"), r"\1"),
    (re.compile(r"\[([^\]]+)\]\[[^\]]*\]"), r"\1"),
    (re.compile(r"<(?:https?://|mailto:)[^>]+>"), ""),
    (re.compile(r"</?[A-Za-z][^>]*>"), ""),
    (re.compile(r"`+([^`]+?)`+"), r"\1"),
    (re.compile(r"(\*\*|__)(?=\S)(.+?)(?<=\S)\1"), r"\2"),
    (re.compile(r"(?<![\w*])\*(?=\S)(.+?)(?<=\S)\*(?![\w*])"), r"\1"),
    (re.compile(r"(?<![\w_])_(?=\S)(.+?)(?<=\S)_(?![\w_])"), r"\1"),
    (re.compile(r"~~(?=\S)(.+?)(?<=\S)~~"), r"\1"),
)
# Escaped characters are literal text: they are hidden from the rules above and restored after.
_ESCAPABLE = "\\`*_{}[]()#+-.!|>~"
_ESCAPE_RE = re.compile(r"\\([" + re.escape(_ESCAPABLE) + r"])")
_PRIVATE_USE_START = 0xE000
_SPACES_RE = re.compile(r"[ \t]+")


class MarkdownBlockKind(StrEnum):
    PARAGRAPH = "paragraph"
    HEADING = "heading"
    LIST_ITEM = "list_item"


@dataclass(frozen=True)
class MarkdownBlock:
    """A heading, list item or paragraph of Markdown, as plain prose."""

    kind: MarkdownBlockKind
    text: str
    heading_level: int = 0
    ordered: bool = False
    depth: int = 0


@dataclass
class _OpenBlock:
    kind: MarkdownBlockKind = MarkdownBlockKind.PARAGRAPH
    ordered: bool = False
    depth: int = 0


class MarkdownBlockParser:
    """Turns Markdown into blocks of plain prose.

    Code, links' URLs, images, tables' rulers and emphasis marks are dropped,
    so they never reach the phrases.
    """

    def parse(self, raw_text: str) -> list[MarkdownBlock]:
        blocks: list[MarkdownBlock] = []
        current: list[str] = []
        shape = _OpenBlock()

        def flush(heading_level: int = 0) -> None:
            nonlocal shape
            if current:
                text = self.inline(" ".join(current))
                if text:
                    kind = MarkdownBlockKind.HEADING if heading_level else shape.kind
                    blocks.append(
                        MarkdownBlock(
                            kind=kind,
                            text=text,
                            heading_level=heading_level,
                            ordered=shape.ordered,
                            depth=shape.depth,
                        )
                    )
                current.clear()
            shape = _OpenBlock()

        for line in self._prose_lines(_COMMENT_RE.sub("", raw_text)):
            setext = _SETEXT_UNDERLINE_RE.match(line)
            if setext and current and shape.kind is MarkdownBlockKind.PARAGRAPH:
                flush(1 if setext.group(1).startswith(_SETEXT_LEVEL_ONE) else 2)
                continue
            if not line.strip() or _RULE_RE.match(line) or _TABLE_DELIMITER_RE.match(line):
                flush()
                continue
            if setext and current:
                flush()
                continue
            if _LINK_DEFINITION_RE.match(line) and not _FOOTNOTE_DEFINITION_RE.match(line):
                continue
            line = _FOOTNOTE_DEFINITION_RE.sub("", _QUOTE_RE.sub("", line))
            heading = _HEADING_RE.match(line)
            list_item = _LIST_ITEM_RE.match(line)
            if heading:
                flush()
                current.append(heading.group(1))
                flush(len(line.strip()) - len(line.strip().lstrip("#")))
            elif _TABLE_ROW_RE.match(line):
                flush()
                for cell in line.strip().strip("|").split("|"):
                    current.append(cell)
                    flush()
            elif list_item:
                flush()
                indent = len(list_item.group(1).expandtabs(_TAB_WIDTH))
                shape = _OpenBlock(
                    kind=MarkdownBlockKind.LIST_ITEM,
                    ordered=list_item.group(2) is not None,
                    depth=indent // _LIST_INDENT,
                )
                current.append(line[list_item.end():])
            else:
                current.append(line.strip())
        flush()
        return blocks

    def inline(self, text: str) -> str:
        """Plain text of one line of Markdown: inline markup dropped, escapes kept literal."""
        text = _ESCAPE_RE.sub(lambda m: _hidden(_ESCAPABLE.index(m.group(1))), text)
        for pattern, replacement in _INLINE_RULES:
            text = pattern.sub(replacement, text)
        for index, char in enumerate(_ESCAPABLE):
            text = text.replace(_hidden(index), char)
        return _SPACES_RE.sub(" ", text).strip()

    def _prose_lines(self, text: str) -> list[str]:
        """Lines outside front matter and fenced code."""
        lines = text.splitlines()
        if lines and lines[0].strip() == _FRONT_MATTER_FENCE:
            closing = next(
                (i for i, line in enumerate(lines[1:], 1) if line.strip() == _FRONT_MATTER_FENCE),
                None,
            )
            if closing is not None:
                lines = lines[closing + 1:]
        prose: list[str] = []
        fence: str | None = None
        for line in lines:
            opening = _FENCE_RE.match(line)
            if fence is None and opening:
                fence = opening.group(1)
                prose.append("")
            elif fence is not None:
                if line.strip().startswith(fence):
                    fence = None
            else:
                prose.append(line)
        return prose


def _hidden(index: int) -> str:
    return chr(_PRIVATE_USE_START + index)
