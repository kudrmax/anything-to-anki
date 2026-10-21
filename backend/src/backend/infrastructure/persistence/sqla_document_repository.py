from __future__ import annotations

import hashlib
from typing import TYPE_CHECKING

from sqlalchemy import func, select

from backend.domain.exceptions import SourceDocumentExistsError
from backend.domain.ports.document_repository import DocumentRepository
from backend.infrastructure.persistence.document_json import dump_document, load_document
from backend.infrastructure.persistence.models import SourceDocumentModel
from backend.infrastructure.persistence.phrase_writes import chunks

if TYPE_CHECKING:
    from collections.abc import Collection

    from sqlalchemy.orm import Session

    from backend.domain.value_objects.document import Document


class SqlaDocumentRepository(DocumentRepository):
    """SQLAlchemy implementation of DocumentRepository."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def save(self, source_id: int, document: Document) -> None:
        stored = self._session.scalar(
            select(SourceDocumentModel.source_id).where(
                SourceDocumentModel.source_id == source_id,
            )
        )
        if stored is not None:
            raise SourceDocumentExistsError(source_id)
        self._session.add(
            SourceDocumentModel(source_id=source_id, document=dump_document(document)),
        )
        self._session.flush()

    def get(self, source_id: int) -> Document | None:
        model = self._session.get(SourceDocumentModel, source_id)
        return load_document(model.document) if model else None

    def fingerprint(self, source_id: int) -> str | None:
        stored = self._session.scalar(
            select(SourceDocumentModel.document).where(
                SourceDocumentModel.source_id == source_id,
            )
        )
        if stored is None:
            return None
        return hashlib.blake2b(stored.encode(), digest_size=16).hexdigest()

    def size_hints(self, source_ids: Collection[int]) -> dict[int, int]:
        hints: dict[int, int] = {}
        for chunk in chunks(sorted(source_ids)):
            hints.update(self._session.execute(
                select(SourceDocumentModel.source_id, func.length(SourceDocumentModel.document))
                .where(SourceDocumentModel.source_id.in_(chunk))
            ).tuples().all())
        return hints
