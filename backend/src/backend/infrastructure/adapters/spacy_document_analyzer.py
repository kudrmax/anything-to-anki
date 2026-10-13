from __future__ import annotations

from typing import TYPE_CHECKING

from backend.domain.ports.document_analyzer import AnalyzedDocument, DocumentAnalyzer
from backend.domain.services.document_layout import DocumentLayout
from backend.domain.value_objects.document import Paragraph, ParagraphMode
from backend.infrastructure.adapters.verse_sentence_ends import VerseSentenceEnds

if TYPE_CHECKING:
    from backend.domain.ports.text_analyzer import TextAnalyzer
    from backend.domain.value_objects.document import Document


class SpacyDocumentAnalyzer(DocumentAnalyzer):
    """Joins the document into one text for spaCy; tokens point back into it by offset.

    Blocks are apart by a blank line, which spaCy never lets a sentence cross. In a paragraph
    of separate lines, a line that completes its sentence ends it.
    """

    def __init__(self, text_analyzer: TextAnalyzer) -> None:
        self._text_analyzer = text_analyzer
        self._verse = VerseSentenceEnds(text_analyzer)

    def analyze(self, document: Document) -> AnalyzedDocument:
        layout = DocumentLayout(document)
        tokens = self._text_analyzer.analyze(layout.text, self._verse_starts(layout))
        return AnalyzedDocument(tokens=tokens, layout=layout)

    def _verse_starts(self, layout: DocumentLayout) -> frozenset[int]:
        starts: set[int] = set()
        for block_index, block in enumerate(layout.document.blocks):
            if not isinstance(block, Paragraph) or block.mode is not ParagraphMode.LINES:
                continue
            ends = self._verse.ends([line.text for line in block.lines])
            starts.update(
                layout.line_offset(block_index, line_index + 1)
                for line_index, ends_sentence in enumerate(ends[:-1])
                if ends_sentence
            )
        return frozenset(starts)
