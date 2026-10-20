"""A source in a real database whose analysis the test writes, for processing and rebuild.

The document has one line per entry of `LINES`; an occurrence on line `n` takes that whole
line as its phrase. A video document times line `n` from `n * LINE_MS` for `SPOKEN_MS`.
"""
from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import MagicMock

from backend.application.dto.analysis_dtos import (
    AnalyzeTextResponse,
    OccurrenceDTO,
    OccurrenceKeyDTO,
    WordDTO,
)
from backend.application.dto.document_dtos import DocumentPositionDTO
from backend.application.use_cases.process_source import ProcessSourceUseCase
from backend.application.use_cases.rebuild_source import RebuildSourceUseCase
from backend.application.use_cases.scope_operation import ScopeOperationUseCase
from backend.application.utils.collected_phrases import CollectedPhrases
from backend.application.utils.decided_elsewhere import DecidedElsewhere
from backend.application.utils.review_progress import ReviewProgress
from backend.application.utils.source_rebuilder import SourceRebuilder
from backend.application.utils.source_scope_resolver import SourceScopeResolver
from backend.domain.entities.candidate_meaning import CandidateMeaning
from backend.domain.entities.candidate_media import CandidateMedia
from backend.domain.services.source_review_status import derive_review_status
from backend.domain.value_objects.document import Document, Line, Paragraph, ParagraphMode
from backend.infrastructure.persistence.database import Base, create_session_factory
from backend.infrastructure.persistence.models import PhraseModel
from backend.infrastructure.persistence.session_change_recorder import SessionChangeRecorder
from backend.infrastructure.persistence.sqla_candidate_meaning_repository import (
    SqlaCandidateMeaningRepository,
)
from backend.infrastructure.persistence.sqla_candidate_media_repository import (
    SqlaCandidateMediaRepository,
)
from backend.infrastructure.persistence.sqla_candidate_repository import SqlaCandidateRepository
from backend.infrastructure.persistence.sqla_card_query import SqlaCardQuery
from backend.infrastructure.persistence.sqla_collection_repository import (
    SqlaCollectionRepository,
)
from backend.infrastructure.persistence.sqla_document_repository import SqlaDocumentRepository
from backend.infrastructure.persistence.sqla_job_repository import SqlaJobRepository
from backend.infrastructure.persistence.sqla_occurrence_repository import (
    SqlaOccurrenceRepository,
)
from backend.infrastructure.persistence.sqla_settings_repository import SqlaSettingsRepository
from backend.infrastructure.persistence.sqla_source_operation_lock import (
    SqlaSourceOperationLock,
)
from backend.infrastructure.persistence.sqla_source_repository import SqlaSourceRepository
from backend.infrastructure.persistence.sqla_unit_of_work import SqlaUnitOfWork
from sqlalchemy import select, text

from tests.candidate_sorter_support import (
    candidate_sorter,
    section_stamper,
    threshold_resolver,
)
from tests.media_files_support import WEIGHT_UNKNOWN, RemovedMediaFiles
from tests.phrase_support import phrase
from tests.source_order_support import added_order
from tests.vocabulary_support import user_vocabulary

if TYPE_CHECKING:
    from pathlib import Path

    from backend.domain.value_objects.held_operation import HeldOperation
    from sqlalchemy.orm import Session, sessionmaker

SOURCE = 1
LINES = (
    "He glared at me.",
    "She glared back.",
    "They glared and left.",
    "We lingered a while.",
    "You lingered too long.",
    "I glared once more.",
)
LINE_MS = 1000
SPOKEN_MS = 900


def document(*, timed: bool = False) -> Document:
    return Document((Paragraph(
        lines=tuple(
            Line(line, i * LINE_MS, i * LINE_MS + SPOKEN_MS) if timed else Line(line)
            for i, line in enumerate(LINES)
        ),
        mode=ParagraphMode.LINES,
    ),))


def time_of_line(line: int) -> tuple[int, int]:
    return line * LINE_MS, line * LINE_MS + SPOKEN_MS


def at(
    line: int, score: float = 50.0, *, text: str | None = None, new: tuple[str, ...] = (),
) -> OccurrenceDTO:
    """An occurrence on `line`; `text` stands in for a phrase the analysis now cuts there;
    `new`: words of the phrase that are new to the user."""
    shown = text if text is not None else LINES[line]
    return OccurrenceDTO(
        phrase=phrase(shown, new=new),
        phrase_position=DocumentPositionDTO(
            block=0, start_line=line, start_char=0, end_line=line, end_char=len(shown),
        ),
        key=OccurrenceKeyDTO(block=0, line=line, char=0),
        fragment_score=score,
    )


def word(lemma: str, *occurrences: OccurrenceDTO, zipf: float = 3.0) -> WordDTO:
    return WordDTO(
        lemma=lemma, pos="VERB", cefr_level=None, zipf_frequency=zipf,
        occurrences=list(occurrences),
    )


class Bench:
    """One content source with its document; `analysis` is what the next analysis finds."""

    def __init__(
        self,
        session: Session,
        *,
        timed: bool = False,
        role: str = "content",
        status: str = "new",
    ) -> None:
        self.session = session
        session.execute(
            text(
                "INSERT INTO sources (id, title, status, role, created_at)"
                " VALUES (:id, 'title', :status, :role, '2026-01-01 00:00:00')"
            ),
            {"id": SOURCE, "status": status, "role": role},
        )
        SqlaDocumentRepository(session).save(SOURCE, document(timed=timed))
        session.commit()
        self.analysis: list[WordDTO] = []
        self.analyze_text = MagicMock()
        self.analyze_text.execute.side_effect = lambda _document, _request: (
            AnalyzeTextResponse(text="", words=self.analysis, total_tokens=0, unique_lemmas=0)
        )
        self.lock = SqlaSourceOperationLock(session)
        self.occurrences = SqlaOccurrenceRepository(session, SessionChangeRecorder(session))
        self.media = SqlaCandidateMediaRepository(session, SessionChangeRecorder(session))
        self.jobs = SqlaJobRepository(session)
        self.candidates = SqlaCandidateRepository(session, SessionChangeRecorder(session))
        self.sources = SqlaSourceRepository(session, SessionChangeRecorder(session))
        self.vocabulary = user_vocabulary()
        self.media_files = RemovedMediaFiles()

    def rebuilder(self) -> SourceRebuilder:
        settings = SqlaSettingsRepository(self.session, SessionChangeRecorder(self.session))
        return SourceRebuilder(
            source_repo=self.sources,
            document_repo=SqlaDocumentRepository(self.session),
            occurrence_repo=self.occurrences,
            job_repo=self.jobs,
            media_repo=self.media,
            media_files=self.media_files,
            settings_repo=settings,
            vocabulary=self.vocabulary,
            threshold_resolver=threshold_resolver(settings),
            stamper=section_stamper(settings),
            analyze_text_use_case=self.analyze_text,
            unit_of_work=SqlaUnitOfWork(self.session, self.vocabulary.scope),
            weight_unknown=WEIGHT_UNKNOWN,
        )

    def rebuild(self) -> RebuildSourceUseCase:
        return RebuildSourceUseCase(
            source_repo=self.sources,
            lock=self.lock,
            unit_of_work=SqlaUnitOfWork(self.session, self.vocabulary.scope),
            rebuilder=self.rebuilder(),
        )

    def scope_operation(
        self, rebuild: RebuildSourceUseCase | None = None,
    ) -> ScopeOperationUseCase:
        """Rebuild and its preview over a set of the bench's sources; nothing to refresh."""
        return ScopeOperationUseCase(
            scope_resolver=SourceScopeResolver(
                self.sources, SqlaCollectionRepository(self.session), added_order(),
            ),
            rebuild_source=rebuild or self.rebuild(),
            refresh_topic=MagicMock(),
            lock=self.lock,
            unit_of_work=SqlaUnitOfWork(self.session, self.vocabulary.scope),
        )

    def process(self) -> ProcessSourceUseCase:
        return ProcessSourceUseCase(
            source_repo=self.sources,
            collected_phrases=CollectedPhrases(
                self.candidates, self.occurrences,
                section_stamper(SqlaSettingsRepository(
                    self.session, SessionChangeRecorder(self.session),
                )),
            ),
            lock=self.lock,
            unit_of_work=SqlaUnitOfWork(self.session, self.vocabulary.scope),
            rebuilder=self.rebuilder(),
        )

    def processed(self, *words: WordDTO) -> None:
        """The source processed with these words found in it."""
        self.analysis = list(words)
        process = self.process()
        process.start(SOURCE)
        self.session.commit()
        process.execute(SOURCE)

    def phrases(self) -> list[PhraseModel]:
        self.session.expire_all()
        return list(self.session.scalars(select(PhraseModel).order_by(PhraseModel.id)))

    def phrase_on(self, lemma: str, line: int) -> PhraseModel:
        word_ids = {w.lemma: w.id for w in self.occurrences.word_rows(SOURCE)}
        return next(
            p for p in self.phrases()
            if p.candidate_id == word_ids[lemma] and p.line == line
        )

    def shown_lines(self, lemma: str) -> list[int | None]:
        word_ids = {w.lemma: w.id for w in self.occurrences.word_rows(SOURCE)}
        return [
            p.line for p in self.phrases()
            if p.candidate_id == word_ids[lemma] and p.shown_by is not None
        ]

    def give_meaning(self, phrase_id: int) -> None:
        word_id = self.session.get(PhraseModel, phrase_id)
        assert word_id is not None
        SqlaCandidateMeaningRepository(
            self.session, SessionChangeRecorder(self.session),
        ).upsert_for_phrase(phrase_id, CandidateMeaning(
            candidate_id=word_id.candidate_id, meaning="to stare angrily", translation=None,
            synonyms=None, examples=None, ipa=None, generated_at=None,
        ))
        self.session.commit()

    def give_clip(self, phrase_id: int, start_ms: int, end_ms: int) -> None:
        self.media.upsert_for_phrase(phrase_id, CandidateMedia(
            candidate_id=0, screenshot_path="/media/1/shot.webp", audio_path="/media/1/clip.m4a",
            start_ms=start_ms, end_ms=end_ms, generated_at=None,
        ))
        self.session.commit()

    def decide_learn(self, lemma: str, phrase_id: int) -> None:
        word_ids = {w.lemma: w.id for w in self.occurrences.word_rows(SOURCE)}
        self.session.execute(
            text("UPDATE candidates SET status = 'learn' WHERE id = :id"),
            {"id": word_ids[lemma]},
        )
        self.set_choice(phrase_id, "learn")
        self.session.commit()

    def set_choice(self, phrase_id: int, choice: str) -> None:
        self.session.execute(
            text("UPDATE phrases SET choice = :choice WHERE id = :id"),
            {"choice": choice, "id": phrase_id},
        )
        self.session.commit()

    def times(self, phrase_id: int) -> tuple[int | None, int | None] | None:
        media = self.media.get_by_phrase_id(phrase_id)
        return (media.start_ms, media.end_ms) if media is not None else None

    def status(self) -> str:
        self.session.expire_all()
        source = self.sources.get_by_id(SOURCE)
        assert source is not None
        return source.status.value

    def review_status(self) -> str:
        """The status the source reads as, from its progress now."""
        self.session.expire_all()
        source = self.sources.get_by_id(SOURCE)
        assert source is not None
        progress = ReviewProgress(
            card_query=SqlaCardQuery(self.session),
            candidate_sorter=candidate_sorter(SqlaSettingsRepository(
                self.session, SessionChangeRecorder(self.session),
            )),
            decided_elsewhere=DecidedElsewhere(self.vocabulary),
        ).of_sources([SOURCE])[SOURCE]
        return derive_review_status(source.status, progress).value


class SharedBench:
    """A bench on a database file, so another session sees only what the bench committed;
    `seen` holds what it saw of the source's operation each time the analysis ran."""

    def __init__(self, path: Path) -> None:
        self._factory: sessionmaker[Session] = create_session_factory(
            f"sqlite:///{path / 'shared.db'}",
        )
        Base.metadata.create_all(self._factory.kw["bind"])
        self.bench = Bench(self._factory())
        self.seen: list[HeldOperation | None] = []
        analyse = self.bench.analyze_text.execute.side_effect

        def look_then_analyse(document: Document, request: object) -> AnalyzeTextResponse:
            self.seen.append(self.held_elsewhere())
            response: AnalyzeTextResponse = analyse(document, request)
            return response

        self.bench.analyze_text.execute.side_effect = look_then_analyse

    def held_elsewhere(self) -> HeldOperation | None:
        with self._factory() as other:
            return SqlaSourceOperationLock(other).operations().get(SOURCE)

    def close(self) -> None:
        self.bench.session.close()
        self._factory.kw["bind"].dispose()
