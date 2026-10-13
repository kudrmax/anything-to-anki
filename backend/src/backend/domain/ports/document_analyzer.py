from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from backend.domain.entities.token_data import TokenData
    from backend.domain.services.document_layout import DocumentLayout
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
    def analyze(self, document: Document) -> AnalyzedDocument: ...
