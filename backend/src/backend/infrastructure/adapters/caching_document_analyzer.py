from __future__ import annotations

import hashlib
import logging
from typing import TYPE_CHECKING

from backend.domain.ports.document_analyzer import AnalyzedDocument, DocumentAnalyzer
from backend.domain.services.document_layout import DocumentLayout

if TYPE_CHECKING:
    from backend.domain.ports.parse_cache import ParseCache
    from backend.domain.value_objects.document import Document

logger = logging.getLogger(__name__)


def document_hash(document: Document) -> str:
    """The document as the analyzer reads it: its plain text."""
    return hashlib.sha256(document.text.encode()).hexdigest()


class CachingDocumentAnalyzer(DocumentAnalyzer):
    """Parses a document once per version of the analyzer; later its tokens come from
    the cache. `version` must change whenever the parse of the same text may change."""

    def __init__(self, inner: DocumentAnalyzer, cache: ParseCache, version: str) -> None:
        self._inner = inner
        self._cache = cache
        self._version = version

    def analyze(self, document: Document) -> AnalyzedDocument:
        key = document_hash(document)
        tokens = self._cache.get(key, self._version)
        if tokens is not None:
            logger.info("document parse: cached (tokens=%d)", len(tokens))
            return AnalyzedDocument(tokens=tokens, layout=DocumentLayout(document))
        analyzed = self._inner.analyze(document)
        self._cache.put(key, self._version, analyzed.tokens)
        return analyzed
