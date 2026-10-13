from __future__ import annotations

from typing import TYPE_CHECKING

from backend.domain.ports.document_repository import DocumentRepository
from backend.infrastructure.persistence.document_json import dump_document, load_document
from backend.infrastructure.persistence.models import SourceDocumentModel

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

    from backend.domain.value_objects.document import Document


class SqlaDocumentRepository(DocumentRepository):
    """SQLAlchemy implementation of DocumentRepository."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def save(self, source_id: int, document: Document) -> None:
        stored = dump_document(document)
        existing = self._session.get(SourceDocumentModel, source_id)
        if existing is None:
            self._session.add(SourceDocumentModel(source_id=source_id, document=stored))
        else:
            existing.document = stored
        self._session.flush()

    def get(self, source_id: int) -> Document | None:
        model = self._session.get(SourceDocumentModel, source_id)
        return load_document(model.document) if model else None
