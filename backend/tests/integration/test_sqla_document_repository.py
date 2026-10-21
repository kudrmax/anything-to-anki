from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from backend.domain.exceptions import SourceDocumentExistsError
from backend.domain.value_objects.document import (
    Document,
    Heading,
    Line,
    ListItem,
    Paragraph,
    ParagraphMode,
)
from backend.infrastructure.persistence.document_json import dump_document
from backend.infrastructure.persistence.sqla_document_repository import SqlaDocumentRepository
from sqlalchemy import text

from tests.integration.conftest import insert_source

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
OTHER = Document(blocks=(Heading(level=1, text="Other"),))


def test_saved_document_reads_back_unchanged(db_session: Session, source_id: int) -> None:
    repo = SqlaDocumentRepository(db_session)

    repo.save(source_id, DOCUMENT)

    assert repo.get(source_id) == DOCUMENT


def test_a_stored_document_is_never_written_again(db_session: Session, source_id: int) -> None:
    """Written once, with its source: what is laid out from it stays true while the stored
    document keeps its fingerprint."""
    repo = SqlaDocumentRepository(db_session)
    repo.save(source_id, DOCUMENT)

    with pytest.raises(SourceDocumentExistsError):
        repo.save(source_id, OTHER)

    assert repo.get(source_id) == DOCUMENT


def test_the_fingerprint_stays_while_the_document_is_stored(db_session: Session) -> None:
    for source_id in (1, 2):
        insert_source(db_session, source_id)
    repo = SqlaDocumentRepository(db_session)
    repo.save(1, DOCUMENT)
    repo.save(2, OTHER)

    assert repo.fingerprint(1) == repo.fingerprint(1)
    assert repo.fingerprint(1) != repo.fingerprint(2)
    assert repo.fingerprint(3) is None


def test_a_source_id_given_again_has_another_fingerprint(
    db_session: Session, source_id: int,
) -> None:
    """SQLite gives the id of the source added last to the next one once it is deleted: the
    new source, made later, has another fingerprint even with the same document."""
    repo = SqlaDocumentRepository(db_session)
    repo.save(source_id, DOCUMENT)
    before = repo.fingerprint(source_id)
    db_session.execute(text("DELETE FROM sources WHERE id = :id"), {"id": source_id})
    db_session.execute(
        text(
            "INSERT INTO sources (id, title, status, created_at)"
            " VALUES (:id, 'title', 'done', '2026-01-01 00:00:00.000001')"
        ),
        {"id": source_id},
    )
    repo.save(source_id, DOCUMENT)

    assert repo.fingerprint(source_id) != before


def test_size_hints_are_the_stored_lengths_of_the_sources_with_a_document(
    db_session: Session, source_id: int,
) -> None:
    insert_source(db_session, source_id + 1)
    repo = SqlaDocumentRepository(db_session)
    repo.save(source_id, DOCUMENT)

    hints = repo.size_hints([source_id, source_id + 1, source_id + 2])

    assert hints == {source_id: len(dump_document(DOCUMENT))}


def test_source_without_document(db_session: Session, source_id: int) -> None:
    assert SqlaDocumentRepository(db_session).get(source_id) is None


def test_deleting_source_deletes_its_document(db_session: Session, source_id: int) -> None:
    repo = SqlaDocumentRepository(db_session)
    repo.save(source_id, DOCUMENT)

    db_session.execute(text("DELETE FROM sources WHERE id = :id"), {"id": source_id})

    assert repo.get(source_id) is None
