from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING

from backend.application.dto.analysis_dtos import AnalyzeTextRequest
from backend.application.utils.occurrence_builder import OccurrenceBuilder
from backend.domain.exceptions import SourceHasNoDocumentError, SourceNotFoundError
from backend.domain.services.card_view import stored_chosen_to_learn
from backend.domain.services.document_time import is_timed, time_of
from backend.domain.services.rebuild_plan import plan_rebuild
from backend.domain.value_objects.source_status import SourceStatus

if TYPE_CHECKING:
    from backend.application.use_cases.analyze_text import AnalyzeTextUseCase
    from backend.application.utils.frequent_word_threshold_resolver import (
        FrequentWordThresholdResolver,
    )
    from backend.application.utils.user_vocabulary import UserVocabulary
    from backend.domain.ports.candidate_media_repository import CandidateMediaRepository
    from backend.domain.ports.document_repository import DocumentRepository
    from backend.domain.ports.job_repository import JobRepository
    from backend.domain.ports.occurrence_repository import OccurrenceRepository
    from backend.domain.ports.settings_repository import SettingsRepository
    from backend.domain.ports.source_repository import SourceRepository
    from backend.domain.ports.unit_of_work import UnitOfWork
    from backend.domain.services.rebuild_plan import RebuildPlan
    from backend.domain.value_objects.built_analysis import BuiltWord
    from backend.domain.value_objects.document import Document
    from backend.domain.value_objects.document_position import DocumentPosition

logger = logging.getLogger(__name__)

DEFAULT_USER_LEVEL = "B1"


@dataclass(frozen=True)
class AnalysedSource:
    """A source's document and what a fresh analysis found in it."""

    source_id: int
    document: Document
    words: list[BuiltWord]


class SourceRebuilder:
    """Analyses a source and applies the analysis without losing the user's work.

    The analysis runs outside any transaction; the plan is made from the phrases as they
    are inside the write transaction that applies it, so work done during the analysis
    counts.
    """

    def __init__(
        self,
        source_repo: SourceRepository,
        document_repo: DocumentRepository,
        occurrence_repo: OccurrenceRepository,
        job_repo: JobRepository,
        media_repo: CandidateMediaRepository,
        settings_repo: SettingsRepository,
        vocabulary: UserVocabulary,
        threshold_resolver: FrequentWordThresholdResolver,
        analyze_text_use_case: AnalyzeTextUseCase,
        unit_of_work: UnitOfWork,
    ) -> None:
        self._source_repo = source_repo
        self._document_repo = document_repo
        self._occurrence_repo = occurrence_repo
        self._job_repo = job_repo
        self._media_repo = media_repo
        self._settings_repo = settings_repo
        self._vocabulary = vocabulary
        self._threshold_resolver = threshold_resolver
        self._analyze_text = analyze_text_use_case
        self._unit_of_work = unit_of_work
        self._builder = OccurrenceBuilder()

    def analyse(self, source_id: int) -> AnalysedSource:
        """Runs outside any transaction: whatever was pending is committed first, so no
        writer waits for the analysis."""
        self._unit_of_work.commit()
        document = self._document_repo.get(source_id)
        if document is None:
            raise SourceHasNoDocumentError(source_id)
        request = AnalyzeTextRequest(
            user_level=self._settings_repo.get("cefr_level", DEFAULT_USER_LEVEL)
            or DEFAULT_USER_LEVEL,
            vocabulary=self._vocabulary.snapshot().without_learning(
                self._learned_here(source_id),
            ),
            frequent_word_zipf=self._threshold_resolver.resolve().zipf,
        )
        result = self._analyze_text.execute(document, request)
        return AnalysedSource(source_id, document, self._builder.words(result.words))

    def _learned_here(self, source_id: int) -> set[str]:
        """Words chosen to learn here, in Anki or not yet, stay its candidates; learned
        elsewhere, they don't."""
        return {
            row.lemma for row in self._occurrence_repo.word_rows(source_id)
            if stored_chosen_to_learn(row.status)
        }

    def plan(self, analysed: AnalysedSource, include_open: bool) -> RebuildPlan:
        """The plan as it stands now; nothing is written."""
        return plan_rebuild(
            analysed.source_id,
            self._occurrence_repo.projection(analysed.source_id),
            self._occurrence_repo.word_rows(analysed.source_id),
            analysed.words,
            include_open,
        )

    def apply(self, analysed: AnalysedSource, include_open: bool) -> RebuildPlan:
        """Plan and write in one write transaction; the source is done after it."""
        source_id = analysed.source_id
        with self._unit_of_work.write():
            source = self._source_repo.get_by_id(source_id)
            if source is None:
                raise SourceNotFoundError(source_id)
            plan = self.plan(analysed, include_open)
            inserted = self._occurrence_repo.apply_plan(plan)
            reset = [u.occurrence_id for u in plan.occ_to_update_text if u.reset_results]
            self._job_repo.cancel_for_phrases([*plan.occ_to_delete, *reset])
            self._time(analysed.document, plan, inserted)
            if source.status is not SourceStatus.DONE:
                self._source_repo.update_status(source_id, SourceStatus.DONE)
        logger.info(
            "rebuild: applied (source_id=%d, include_open=%s, words +%d -%d, phrases +%d "
            "~%d -%d)",
            source_id, include_open, len(plan.words_to_create), len(plan.words_to_delete),
            len(plan.occ_to_insert), len(plan.occ_to_update_text), len(plan.occ_to_delete),
        )
        return plan

    def _time(self, document: Document, plan: RebuildPlan, inserted: list[int]) -> None:
        """Phrases of a video whose text the plan wrote get the time of their lines."""
        if not is_timed(document):
            return
        positions: dict[int, DocumentPosition] = {
            u.occurrence_id: u.phrase_position for u in plan.occ_to_update_text
        }
        for phrase_id, planned in zip(inserted, plan.occ_to_insert, strict=True):
            positions[phrase_id] = planned.occurrence.phrase_position
        self._media_repo.set_timecodes({
            phrase_id: time_of(document, position) for phrase_id, position in positions.items()
        })

