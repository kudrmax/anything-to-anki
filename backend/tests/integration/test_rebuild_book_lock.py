"""A worker writing while the plan of a book is applied waits for it, and gets through
well within SQLite's busy timeout: applying a book takes seconds, not the whole timeout."""
from __future__ import annotations

import logging
import threading
import time
from typing import TYPE_CHECKING
from unittest.mock import MagicMock

import pytest
from backend.application.dto.analysis_dtos import (
    AnalyzeTextResponse,
    OccurrenceDTO,
    OccurrenceKeyDTO,
    WordDTO,
)
from backend.application.dto.document_dtos import DocumentPositionDTO
from backend.application.utils.source_rebuilder import SourceRebuilder
from backend.domain.value_objects.document import Document, Line, Paragraph, ParagraphMode
from backend.domain.value_objects.rebuild_mode import RebuildMode
from backend.infrastructure.persistence.database import (
    SQLITE_BUSY_TIMEOUT_MS,
    Base,
    create_session_factory,
)
from backend.infrastructure.persistence.session_change_recorder import SessionChangeRecorder
from backend.infrastructure.persistence.sqla_anki_sync_repository import SqlaAnkiSyncRepository
from backend.infrastructure.persistence.sqla_candidate_media_repository import (
    SqlaCandidateMediaRepository,
)
from backend.infrastructure.persistence.sqla_document_repository import SqlaDocumentRepository
from backend.infrastructure.persistence.sqla_job_repository import SqlaJobRepository
from backend.infrastructure.persistence.sqla_occurrence_repository import (
    SqlaOccurrenceRepository,
)
from backend.infrastructure.persistence.sqla_settings_repository import SqlaSettingsRepository
from backend.infrastructure.persistence.sqla_source_repository import SqlaSourceRepository
from backend.infrastructure.persistence.sqla_unit_of_work import SqlaUnitOfWork
from sqlalchemy import text

from tests.candidate_sorter_support import section_stamper, threshold_resolver
from tests.document_support import put_document
from tests.media_files_support import WEIGHT_UNKNOWN, RemovedMediaFiles
from tests.phrase_support import phrase
from tests.vocabulary_support import user_vocabulary

if TYPE_CHECKING:
    from pathlib import Path

    from backend.domain.services.rebuild_plan import RebuildPlan
    from sqlalchemy.orm import Session, sessionmaker

pytestmark = pytest.mark.integration
logger = logging.getLogger(__name__)

SOURCE = 1
BOOK_WORDS = 4_000
PHRASES_PER_WORD = 3.2
BOOK_PHRASES = int(BOOK_WORDS * PHRASES_PER_WORD)
LINE_MS = 2_000
# Well under the busy timeout: a worker must never come near failing on a book.
APPLY_BUDGET_S = SQLITE_BUSY_TIMEOUT_MS / 1000 / 3


def _line(n: int, *, edition: int) -> str:
    return f"Line {n} of the book, edition {edition}."


def _book(edition: int) -> Document:
    return Document((Paragraph(
        lines=tuple(
            Line(_line(n, edition=edition), n * LINE_MS, n * LINE_MS + LINE_MS // 2)
            for n in range(BOOK_PHRASES)
        ),
        mode=ParagraphMode.LINES,
    ),))


def _analysis(edition: int) -> list[WordDTO]:
    """Every word on its own lines, each line one phrase; `edition` changes every text."""
    words: list[WordDTO] = []
    for w in range(BOOK_WORDS):
        lines = range(w, BOOK_PHRASES, BOOK_WORDS)
        words.append(WordDTO(
            lemma=f"word{w}", pos="NOUN", cefr_level=None, zipf_frequency=3.0,
            occurrences=[_occurrence(n, edition) for n in lines],
        ))
    return words


def _occurrence(line: int, edition: int) -> OccurrenceDTO:
    shown = _line(line, edition=edition)
    return OccurrenceDTO(
        phrase=phrase(shown),
        phrase_position=DocumentPositionDTO(
            block=0, start_line=line, start_char=0, end_line=line, end_char=len(shown),
        ),
        key=OccurrenceKeyDTO(block=0, line=line, char=0),
        fragment_score=float(line % 7),
    )


class _WorkerDuringApply:
    """Starts a worker-style write on its own connection once the write transaction holds
    the database, then lets the plan be applied."""

    def __init__(self, repo: SqlaOccurrenceRepository, factory: sessionmaker[Session]) -> None:
        self._repo = repo
        self._factory = factory
        self.waited_s: float | None = None
        self.error: BaseException | None = None
        self.thread: threading.Thread | None = None

    def __getattr__(self, name: str) -> object:
        return getattr(self._repo, name)

    def apply_plan(self, plan: RebuildPlan) -> list[int]:
        self.thread = threading.Thread(target=self._write)
        self.thread.start()
        return self._repo.apply_plan(plan)

    def _write(self) -> None:
        started = time.perf_counter()
        session = self._factory()
        try:
            session.execute(text("UPDATE sources SET title = 'worker was here' WHERE id = :id"),
                            {"id": SOURCE})
            session.commit()
            self.waited_s = time.perf_counter() - started
        except BaseException as e:  # noqa: BLE001 — reported to the test
            self.error = e
        finally:
            session.close()


def _rebuilder(
    session: Session, worker: _WorkerDuringApply, words: list[WordDTO],
) -> SourceRebuilder:
    settings = SqlaSettingsRepository(session, SessionChangeRecorder(session))
    analyze = MagicMock()
    analyze.execute.return_value = AnalyzeTextResponse(
        text="", words=words, total_tokens=0, unique_lemmas=0,
    )
    sources = SqlaSourceRepository(session, SessionChangeRecorder(session))
    vocabulary = user_vocabulary()
    return SourceRebuilder(
        source_repo=sources,
        document_repo=SqlaDocumentRepository(session),
        occurrence_repo=worker,  # type: ignore[arg-type]
        anki_sync=SqlaAnkiSyncRepository(session, SessionChangeRecorder(session)),
        job_repo=SqlaJobRepository(session, SessionChangeRecorder(session)),
        media_repo=SqlaCandidateMediaRepository(session, SessionChangeRecorder(session)),
        media_files=RemovedMediaFiles(),
        settings_repo=settings,
        vocabulary=vocabulary,
        threshold_resolver=threshold_resolver(settings),
        stamper=section_stamper(settings),
        analyze_text_use_case=analyze,
        unit_of_work=SqlaUnitOfWork(session, vocabulary.scope),
        weight_unknown=WEIGHT_UNKNOWN,
    )


def _apply(factory: sessionmaker[Session], edition: int) -> tuple[float, _WorkerDuringApply]:
    session = factory()
    try:
        put_document(session, SOURCE, _book(edition))
        session.commit()
        worker = _WorkerDuringApply(SqlaOccurrenceRepository(
            session, SessionChangeRecorder(session),
        ), factory)
        rebuilder = _rebuilder(session, worker, _analysis(edition))
        analysed = rebuilder.analyse(SOURCE)
        started = time.perf_counter()
        rebuilder.apply(analysed, RebuildMode.UPDATE)
        elapsed = time.perf_counter() - started
    finally:
        session.close()
    assert worker.thread is not None
    worker.thread.join(timeout=SQLITE_BUSY_TIMEOUT_MS / 1000)
    return elapsed, worker


def test_a_worker_gets_through_while_a_book_is_applied(tmp_path: Path) -> None:
    factory = create_session_factory(f"sqlite:///{tmp_path / 'book.db'}")
    Base.metadata.create_all(factory.kw["bind"])
    with factory() as session:
        session.execute(text(
            "INSERT INTO sources (id, title, status, role, created_at)"
            " VALUES (:id, 'book', 'new', 'content', '2026-01-01 00:00:00')"
        ), {"id": SOURCE})
        session.commit()

    for edition, what in ((1, "first build"), (2, "every text changed")):
        elapsed, worker = _apply(factory, edition)
        logger.warning(
            "book apply (%s): %.2f s, worker waited %.2f s",
            what, elapsed, worker.waited_s or -1,
        )
        print(f"book apply ({what}): {elapsed:.2f} s, worker waited {worker.waited_s:.2f} s")
        assert worker.error is None
        assert worker.waited_s is not None
        assert elapsed < APPLY_BUDGET_S
        assert worker.waited_s < SQLITE_BUSY_TIMEOUT_MS / 1000

    with factory() as session:
        phrases = session.execute(text("SELECT count(*) FROM phrases")).scalar_one()
        timed = session.execute(
            text("SELECT count(*) FROM candidate_media WHERE start_ms IS NOT NULL")
        ).scalar_one()
    assert phrases == BOOK_PHRASES
    assert timed == BOOK_PHRASES
