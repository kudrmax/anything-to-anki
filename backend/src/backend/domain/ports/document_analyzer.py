from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import TYPE_CHECKING

from backend.domain.services.long_operation_progress import no_report

if TYPE_CHECKING:
    from backend.domain.entities.token_data import TokenData
    from backend.domain.services.document_layout import DocumentLayout
    from backend.domain.services.long_operation_progress import PartReport
    from backend.domain.value_objects.document import Document


@dataclass(frozen=True)
class AnalyzedDocument:
    """Tokens of a document; their offsets point into the layout's text."""

    tokens: list[TokenData]
    layout: DocumentLayout


class DocumentAnalyzer(ABC):
    """NLP analysis of a document: a sentence never runs across blocks, and in a paragraph
    of separate lines a line that completes a sentence ends it."""

    @abstractmethod
    def analyze(self, document: Document, report: PartReport = no_report) -> AnalyzedDocument:
        """`report` is told the share of the document analysed, ending at 1."""
