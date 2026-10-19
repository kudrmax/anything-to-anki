from __future__ import annotations

import bisect
from dataclasses import replace
from typing import TYPE_CHECKING

from backend.domain.ports.document_analyzer import AnalyzedDocument, DocumentAnalyzer
from backend.domain.services.document_layout import DocumentLayout
from backend.domain.value_objects.document import Paragraph, ParagraphMode
from backend.infrastructure.adapters.verse_sentence_ends import VerseSentenceEnds

if TYPE_CHECKING:
    from backend.domain.entities.token_data import TokenData
    from backend.domain.value_objects.document import Document
    from backend.infrastructure.adapters.spacy_text_analyzer import SpaCyTextAnalyzer

# Bump whenever the tokens of the same text may change outside spaCy and its model: here,
# in SpaCyTextAnalyzer, VerseSentenceEnds or TokenData. Cached parses of older versions
# are not used.
POSTPROCESS_VERSION = 1

# Ends a line of verse for the parser; it is never part of the document or of a phrase.
SENTENCE_END = "."


class SpacyDocumentAnalyzer(DocumentAnalyzer):
    """Joins the document into one text for spaCy; tokens point back into it by offset.

    Blocks are apart by a blank line, which spaCy never lets a sentence cross. In a paragraph
    of separate lines, a line that completes its sentence gets a period the parser alone sees:
    it parses the line as the sentence it is. The period's token keeps no text.
    """

    def __init__(self, text_analyzer: SpaCyTextAnalyzer) -> None:
        self._text_analyzer = text_analyzer
        self._verse = VerseSentenceEnds(text_analyzer)

    @property
    def version(self) -> str:
        """Changes whenever the parse of the same document may change."""
        return f"{self._text_analyzer.version}:{POSTPROCESS_VERSION}"

    def analyze(self, document: Document) -> AnalyzedDocument:
        layout = DocumentLayout(document)
        ends = self._verse_ends(layout)
        parsed = "".join(
            layout.text[start:end] + (SENTENCE_END if end in ends else "")
            for start, end in _pieces(layout.text, ends)
        )
        tokens = [
            _placed(token, ends) for token in self._text_analyzer.analyze(parsed)
        ]
        return AnalyzedDocument(tokens=tokens, layout=layout)

    def _verse_ends(self, layout: DocumentLayout) -> list[int]:
        """Where lines of verse end their sentences, in the document's text."""
        ends: list[int] = []
        for block_index, block in enumerate(layout.document.blocks):
            if not isinstance(block, Paragraph) or block.mode is not ParagraphMode.LINES:
                continue
            ending = self._verse.ends([line.text for line in block.lines])
            ends.extend(
                layout.line_offset(block_index, line_index) + len(line.text)
                for line_index, (line, ends_sentence) in enumerate(
                    zip(block.lines, ending, strict=True),
                )
                if ends_sentence
            )
        return sorted(ends)


def _pieces(text: str, cuts: list[int]) -> list[tuple[int, int]]:
    bounds = [0, *cuts, len(text)]
    return list(zip(bounds, bounds[1:], strict=False))


def _placed(token: TokenData, ends: list[int]) -> TokenData:
    """A token's offset in the document: periods the parser alone saw are taken out."""
    added_before = bisect.bisect_left([end + i for i, end in enumerate(ends)], token.char_start)
    if added_before < len(ends) and ends[added_before] + added_before == token.char_start:
        return replace(token, text="", char_start=ends[added_before])
    return replace(token, char_start=token.char_start - added_before)
