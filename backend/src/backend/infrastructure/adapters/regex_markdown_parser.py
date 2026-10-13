from __future__ import annotations

import re

from backend.domain.ports.source_parser import SourceParser

PARAGRAPH_SEPARATOR = "\n\n"

_FENCE_RE = re.compile(r"^\s*(```|~~~)")
_FRONT_MATTER_FENCE = "---"
_COMMENT_RE = re.compile(r"<!--.*?-->", re.DOTALL)
_HEADING_RE = re.compile(r"^\s{0,3}#{1,6}\s+(.*?)(?:\s+#+)?\s*$")
_SETEXT_UNDERLINE_RE = re.compile(r"^\s{0,3}(=+|-+)\s*$")
_RULE_RE = re.compile(r"^\s{0,3}([-*_])(\s*\1){2,}\s*$")
_QUOTE_RE = re.compile(r"^\s{0,3}(>\s?)+")
_LIST_ITEM_RE = re.compile(r"^\s*(?:[-*+]|\d{1,9}[.)])\s+(?:\[[ xX]\]\s+)?")
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


class RegexMarkdownParser(SourceParser):
    """Turns Markdown into plain prose: one paragraph per heading, list item or paragraph.

    Code, links' URLs, images, tables' rulers and emphasis marks are dropped,
    so they never reach the phrases.
    """

    def parse(self, raw_text: str) -> str:
        blocks: list[str] = []
        current: list[str] = []

        def flush() -> None:
            if current:
                text = self._inline(" ".join(current))
                if text:
                    blocks.append(text)
                current.clear()

        for line in self._prose_lines(_COMMENT_RE.sub("", raw_text)):
            if not line.strip() or _RULE_RE.match(line) or _TABLE_DELIMITER_RE.match(line):
                flush()
                continue
            if _SETEXT_UNDERLINE_RE.match(line) and current:
                flush()
                continue
            if _LINK_DEFINITION_RE.match(line) and not _FOOTNOTE_DEFINITION_RE.match(line):
                continue
            line = _FOOTNOTE_DEFINITION_RE.sub("", _QUOTE_RE.sub("", line))
            heading = _HEADING_RE.match(line)
            if heading:
                flush()
                current.append(heading.group(1))
                flush()
            elif _TABLE_ROW_RE.match(line):
                flush()
                for cell in line.strip().strip("|").split("|"):
                    current.append(cell)
                    flush()
            elif _LIST_ITEM_RE.match(line):
                flush()
                current.append(_LIST_ITEM_RE.sub("", line, count=1))
            else:
                current.append(line.strip())
        flush()
        return PARAGRAPH_SEPARATOR.join(blocks)

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

    def _inline(self, text: str) -> str:
        text = _ESCAPE_RE.sub(lambda m: _hidden(_ESCAPABLE.index(m.group(1))), text)
        for pattern, replacement in _INLINE_RULES:
            text = pattern.sub(replacement, text)
        for index, char in enumerate(_ESCAPABLE):
            text = text.replace(_hidden(index), char)
        return _SPACES_RE.sub(" ", text).strip()


def _hidden(index: int) -> str:
    return chr(_PRIVATE_USE_START + index)
