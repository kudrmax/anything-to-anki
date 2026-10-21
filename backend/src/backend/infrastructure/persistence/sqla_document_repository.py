from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import func, literal_column, select

from backend.domain.exceptions import SourceDocumentExistsError
from backend.domain.ports.document_repository import DocumentRepository
from backend.domain.value_objects.document import (
    BLOCK_SEPARATOR,
    FLOW_LINE_SEPARATOR,
)
from backend.infrastructure.persistence.document_json import dump_document, load_document
from backend.infrastructure.persistence.models import SourceDocumentModel, SourceModel
from backend.infrastructure.persistence.phrase_writes import chunks

if TYPE_CHECKING:
    from collections.abc import Collection

    from sqlalchemy import ColumnClause
    from sqlalchemy.orm import Session

    from backend.domain.value_objects.document import Document

# The length of `Document.text` from the stored JSON, without loading it: the text of every
# line and heading, a line separator between lines of a block (one character in either mode)
# and BLOCK_SEPARATOR between blocks. T text values in B blocks have T - B line separators.
_LINE_SEPARATOR_CHARS = len(FLOW_LINE_SEPARATOR)
_TEXT_LENGTH: ColumnClause[int] = literal_column(
    f"max(0, (SELECT coalesce(sum(length(value)), 0) + {_LINE_SEPARATOR_CHARS} * count(*)"
    " FROM json_tree(source_documents.document) WHERE key = 'text')"
    f" + {len(BLOCK_SEPARATOR) - _LINE_SEPARATOR_CHARS}"
    " * json_array_length(source_documents.document, '$.blocks')"
    f" - {len(BLOCK_SEPARATOR)})"
)


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
        """The moment its source was made, to the microsecond, and its size in bytes, which
        SQLite reads from the record's header without reading the document."""
        stored = self._session.execute(
            select(SourceModel.created_at, func.octet_length(SourceDocumentModel.document))
            .join(SourceModel, SourceModel.id == SourceDocumentModel.source_id)
            .where(SourceDocumentModel.source_id == source_id)
        ).tuples().first()
        if stored is None:
            return None
        created_at, length = stored
        return f"{created_at.isoformat()}/{length}"

    def size_hints(self, source_ids: Collection[int]) -> dict[int, int]:
        hints: dict[int, int] = {}
        for chunk in chunks(sorted(source_ids)):
            hints.update(self._session.execute(
                select(SourceDocumentModel.source_id, _TEXT_LENGTH)
                .where(SourceDocumentModel.source_id.in_(chunk))
            ).tuples().all())
        return hints
