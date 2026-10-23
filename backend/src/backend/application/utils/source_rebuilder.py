from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING

from backend.application.dto.analysis_dtos import AnalyzeTextRequest
from backend.application.utils.occurrence_builder import OccurrenceBuilder
from backend.domain.exceptions import SourceHasNoDocumentError, SourceNotFoundError
from backend.domain.services.card_view import stored_chosen_to_learn
from backend.domain.services.document_time import is_timed, time_of
from backend.domain.services.long_operation_progress import no_report
from backend.domain.services.phrase_selection import SelectionScore
from backend.domain.services.rebuild_plan import RebuildRules, plan_rebuild, plan_sections
from backend.domain.value_objects.source_status import SourceStatus

if TYPE_CHECKING:
    from collections.abc import Sequence

    from backend.application.use_cases.analyze_text import AnalyzeTextUseCase
    from backend.application.utils.frequent_word_threshold_resolver import (
        FrequentWordThresholdResolver,
    )
    from backend.application.utils.section_stamper import SectionStamper
    from backend.application.utils.user_vocabulary import UserVocabulary
    from backend.domain.ports.anki_sync_repository import AnkiSyncRepository
    from backend.domain.ports.candidate_media_repository import CandidateMediaRepository
    from backend.domain.ports.document_repository import DocumentRepository
    from backend.domain.ports.job_repository import JobRepository
    from backend.domain.ports.media_files import MediaFiles
    from backend.domain.ports.occurrence_repository import OccurrenceRepository
    from backend.domain.ports.settings_repository import SettingsRepository
    from backend.domain.ports.source_repository import SourceRepository
    from backend.domain.ports.unit_of_work import UnitOfWork
    from backend.domain.services.long_operation_progress import PartReport
    from backend.domain.services.rebuild_plan import RebuildPlan
    from backend.domain.value_objects.built_analysis import BuiltWord, WordKey
    from backend.domain.value_objects.document import Document
    from backend.domain.value_objects.document_position import DocumentPosition
    from backend.domain.value_objects.rebuild_mode import RebuildMode

logger = logging.getLogger(__name__)

DEFAULT_USER_LEVEL = "B1"


@dataclass(frozen=True)
class AnalysedSource:
    """A source's document and what a fresh analysis found in it; a source without text of
    its own has neither. `done_on_the_fly`: its words the user knows or learns via another
    source, as the analysis saw them."""

    source_id: int
    document: Document | None
    words: list[BuiltWord] | None
    done_on_the_fly: frozenset[WordKey] = frozenset()


@dataclass(frozen=True)
class AnalysisValues:
    """The settings an analysis runs with, given rather than read: a level change analyses
    with the values it has not saved yet."""

    user_level: str
    frequent_word_zipf: float | None


@dataclass(frozen=True)
class AppliedSource:
    """What applying a source wrote, and the files of what it dropped, to remove once the
    write is committed."""

    plan: RebuildPlan
    dropped_files: list[str]


class SourceRebuilder:
    """Analyses a source and applies the analysis without losing the user's work.

    The analysis runs outside any transaction; the plan is made from the phrases as they
    are inside the write transaction that applies it, so work done during the analysis
    counts. Files of what the plan drops go once it is committed.

    `weight_unknown`: the weight the analysis gives a new word in a phrase's score.
    """

    def __init__(
        self,
        source_repo: SourceRepository,
        document_repo: DocumentRepository,
        occurrence_repo: OccurrenceRepository,
        anki_sync: AnkiSyncRepository,
        job_repo: JobRepository,
        media_repo: CandidateMediaRepository,
        media_files: MediaFiles,
        settings_repo: SettingsRepository,
        vocabulary: UserVocabulary,
        threshold_resolver: FrequentWordThresholdResolver,
        stamper: SectionStamper,
        analyze_text_use_case: AnalyzeTextUseCase,
        unit_of_work: UnitOfWork,
        weight_unknown: int,
    ) -> None:
        self._source_repo = source_repo
        self._document_repo = document_repo
        self._occurrence_repo = occurrence_repo
        self._anki_sync = anki_sync
        self._job_repo = job_repo
        self._media_repo = media_repo
        self._media_files = media_files
        self._settings_repo = settings_repo
        self._vocabulary = vocabulary
        self._threshold_resolver = threshold_resolver
        self._stamper = stamper
        self._analyze_text = analyze_text_use_case
        self._unit_of_work = unit_of_work
        self._weight_unknown = weight_unknown
        self._builder = OccurrenceBuilder()

    def analyse(
        self,
        source_id: int,
        values: AnalysisValues | None = None,
        report: PartReport = no_report,
    ) -> AnalysedSource:
        """Runs outside any write transaction, so no writer waits for the analysis. With no
        `values`, it reads them from the settings. `report` is told the share analysed."""
        source = self._source_repo.get_by_id(source_id)
        if source is not None and not source.has_text:
            report(1.0)
            return AnalysedSource(source_id, None, None)
        document = self._document_repo.get(source_id)
        if document is None:
            raise SourceHasNoDocumentError(source_id)
        values = values or self._saved_values()
        request = AnalyzeTextRequest(
            user_level=values.user_level,
            vocabulary=self._vocabulary.snapshot().without_learning(
                self._learned_here(source_id),
            ),
            frequent_word_zipf=values.frequent_word_zipf,
        )
        result = self._analyze_text.execute(document, request, report)
        return AnalysedSource(
            source_id, document, self._builder.words(result.words),
            self._done_on_the_fly(source_id),
        )

    def sizes(self, source_ids: Sequence[int]) -> dict[int, int]:
        """The length of each source's text, of those that have one."""
        return self._document_repo.size_hints(source_ids)

    def _saved_values(self) -> AnalysisValues:
        return AnalysisValues(
            user_level=self._settings_repo.get("cefr_level", DEFAULT_USER_LEVEL)
            or DEFAULT_USER_LEVEL,
            frequent_word_zipf=self._threshold_resolver.resolve().zipf,
        )

    def _learned_here(self, source_id: int) -> set[str]:
        """Words chosen to learn here, in Anki or not yet, stay its candidates; learned
        elsewhere, they don't."""
        return {
            row.lemma for row in self._occurrence_repo.word_rows(source_id)
            if stored_chosen_to_learn(row.status)
        }

    def _done_on_the_fly(self, source_id: int) -> frozenset[WordKey]:
        return frozenset(
            row.key for row in self._occurrence_repo.word_rows(source_id)
            if self._vocabulary.of(row.lemma).elsewhere is not None
        )

    def plan(self, analysed: AnalysedSource, mode: RebuildMode) -> RebuildPlan:
        """The plan as it stands now; nothing is written. A source without text of its own
        has its sections moved only, whatever the mode."""
        sections = self._stamper.rule()
        if analysed.words is None:
            return plan_sections(
                analysed.source_id,
                self._occurrence_repo.projection(analysed.source_id),
                self._occurrence_repo.word_rows(analysed.source_id),
                sections,
            )
        return plan_rebuild(
            analysed.source_id,
            self._occurrence_repo.projection(analysed.source_id),
            self._occurrence_repo.word_rows(analysed.source_id),
            analysed.words,
            RebuildRules(
                mode=mode,
                sections=sections,
                score=SelectionScore(sections.knowledge, self._weight_unknown),
                done_on_the_fly=analysed.done_on_the_fly,
            ),
        )

    def apply(self, analysed: AnalysedSource, mode: RebuildMode) -> RebuildPlan:
        """Plan and write in one write transaction; the source is done after it."""
        with self._unit_of_work.write():
            applied = self.apply_inside(analysed, mode)
        self._media_files.remove(applied.dropped_files)
        return applied.plan

    def apply_inside(self, analysed: AnalysedSource, mode: RebuildMode) -> AppliedSource:
        """Plan and write inside the caller's write transaction; its caller removes the
        dropped files once that is committed."""
        source_id = analysed.source_id
        source = self._source_repo.get_by_id(source_id)
        if source is None:
            raise SourceNotFoundError(source_id)
        plan = self.plan(analysed, mode)
        # A word goes only with its last phrase, so the phrases cover the words too.
        self._anki_sync.orphan(plan.occ_to_delete)
        applied = self._occurrence_repo.apply_plan(plan)
        self._job_repo.cancel_for_phrases(list(plan.occ_to_delete))
        self._time(analysed.document, plan, applied.inserted)
        if source.status is not SourceStatus.DONE:
            self._source_repo.update_status(source_id, SourceStatus.DONE)
        logger.info(
            "rebuild: applied (source_id=%d, mode=%s, words +%d -%d, phrases +%d ~%d -%d, "
            "files -%d)",
            source_id, mode, len(plan.words_to_create), len(plan.words_to_delete),
            len(plan.occ_to_insert), len(plan.occ_to_update_text), len(plan.occ_to_delete),
            len(applied.dropped_files),
        )
        return AppliedSource(plan, applied.dropped_files)

    def _time(self, document: Document | None, plan: RebuildPlan, inserted: list[int]) -> None:
        """Phrases of a video whose text the plan wrote get the time of their lines."""
        if document is None or not is_timed(document):
            return
        positions: dict[int, DocumentPosition] = {
            u.occurrence_id: u.phrase_position for u in plan.occ_to_update_text
        }
        for phrase_id, planned in zip(inserted, plan.occ_to_insert, strict=True):
            positions[phrase_id] = planned.occurrence.phrase_position
        self._media_repo.set_timecodes({
            phrase_id: time_of(document, position) for phrase_id, position in positions.items()
        })

