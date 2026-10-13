from __future__ import annotations

from backend.domain.ports.source_parser import SourceParser
from backend.infrastructure.adapters.markdown_blocks import MarkdownBlockParser

PARAGRAPH_SEPARATOR = "\n\n"


class RegexMarkdownParser(SourceParser):
    """Turns Markdown into plain prose: one paragraph per heading, list item or paragraph."""

    def __init__(self) -> None:
        self._blocks = MarkdownBlockParser()

    def parse(self, raw_text: str) -> str:
        return PARAGRAPH_SEPARATOR.join(block.text for block in self._blocks.parse(raw_text))
