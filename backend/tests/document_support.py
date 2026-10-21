"""Another text for a source that has one: the app never rewrites a stored document, so a test
that needs one puts it in place of the old one directly."""
from __future__ import annotations

from typing import TYPE_CHECKING

from backend.infrastructure.persistence.models import SourceDocumentModel
from backend.infrastructure.persistence.sqla_document_repository import SqlaDocumentRepository
from sqlalchemy import delete

if TYPE_CHECKING:
    from backend.domain.value_objects.document import Document
    from sqlalchemy.orm import Session


def put_document(session: Session, source_id: int, document: Document) -> None:
    """The source's document becomes `document`, whatever it had."""
    session.execute(delete(SourceDocumentModel).where(SourceDocumentModel.source_id == source_id))
    SqlaDocumentRepository(session).save(source_id, document)
