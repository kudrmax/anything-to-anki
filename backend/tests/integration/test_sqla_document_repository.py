from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from backend.domain.value_objects.document import (
    Document,
    Heading,
    Line,
    ListItem,
    Paragraph,
    ParagraphMode,
)
from backend.infrastructure.persistence.sqla_document_repository import SqlaDocumentRepository
from sqlalchemy import text

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

pytestmark = pytest.mark.integration

DOCUMENT = Document(
    blocks=(
        Heading(level=1, text="Part 1"),
        Heading(level=2, text="Chapter 1"),
        Paragraph(lines=(Line("It started — «here» 😀."),), mode=ParagraphMode.FLOW),
        ListItem(lines=(Line("First point"), Line("goes on")), ordered=True, depth=1),
        Paragraph(
            lines=(Line("Hello darkness, my old friend"), Line("I've come to talk with you")),
            mode=ParagraphMode.LINES,
        ),
        Paragraph(
            lines=(Line("I told him", start_ms=0, end_ms=1500), Line("nothing.", 1600, 2100)),
            mode=ParagraphMode.FLOW,
        ),
    )
)


def test_saved_document_reads_back_unchanged(db_session: Session, source_id: int) -> None:
    repo = SqlaDocumentRepository(db_session)

    repo.save(source_id, DOCUMENT)

    assert repo.get(source_id) == DOCUMENT


def test_saving_again_replaces_the_document(db_session: Session, source_id: int) -> None:
    repo = SqlaDocumentRepository(db_session)
    replacement = Document(blocks=(Heading(level=1, text="Other"),))

    repo.save(source_id, DOCUMENT)
    repo.save(source_id, replacement)

    assert repo.get(source_id) == replacement


def test_source_without_document(db_session: Session, source_id: int) -> None:
    assert SqlaDocumentRepository(db_session).get(source_id) is None


def test_deleting_source_deletes_its_document(db_session: Session, source_id: int) -> None:
    repo = SqlaDocumentRepository(db_session)
    repo.save(source_id, DOCUMENT)

    db_session.execute(text("DELETE FROM sources WHERE id = :id"), {"id": source_id})

    assert repo.get(source_id) is None
