from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from backend.application.dto.analysis_dtos import AnalyzeTextRequest
from backend.application.dto.cefr_dtos import dto_to_breakdown
from backend.application.utils.timecode_mapping import find_timecodes
from backend.domain.entities.candidate_media import CandidateMedia
from backend.domain.entities.stored_candidate import StoredCandidate
from backend.domain.exceptions import SourceAlreadyProcessedError, SourceNotFoundError
from backend.domain.value_objects.candidate_status import CandidateStatus
from backend.domain.value_objects.enrichment_status import EnrichmentStatus
from backend.domain.value_objects.processing_stage import ProcessingStage
from backend.domain.value_objects.source_status import SourceStatus
from backend.domain.value_objects.content_type import ContentType
from backend.domain.value_objects.input_method import InputMethod

if TYPE_CHECKING:
    from collections.abc import Callable

    from backend.application.use_cases.analyze_text import AnalyzeTextUseCase
    from backend.domain.ports.candidate_media_repository import CandidateMediaRepository
    from backend.domain.ports.candidate_repository import CandidateRepository
    from backend.domain.ports.known_word_repository import KnownWordRepository
    from backend.domain.ports.settings_repository import SettingsRepository
    from backend.domain.ports.source_parser import SourceParser
    from backend.domain.ports.source_repository import SourceRepository
    from backend.domain.ports.structured_srt_parser import StructuredSrtParser
    from backend.domain.value_objects.parsed_srt import ParsedSrt

logger = logging.getLogger(__name__)

_ALLOWED_START_STATUSES = frozenset({SourceStatus.NEW, SourceStatus.ERROR})


class ProcessSourceUseCase:
    """Orchestrates async source processing: validates, runs pipeline, saves results."""

    def __init__(
        self,
        source_repo: SourceRepository,
        candidate_repo: CandidateRepository,
        known_word_repo: KnownWordRepository,
        settings_repo: SettingsRepository,
        analyze_text_use_case: AnalyzeTextUseCase,
        source_parsers: dict[InputMethod, SourceParser] | None = None,
        structured_srt_parser: StructuredSrtParser | None = None,
        media_repo: CandidateMediaRepository | None = None,
    ) -> None:
        self._source_repo = source_repo
        self._candidate_repo = candidate_repo
        self._known_word_repo = known_word_repo
        self._settings_repo = settings_repo
        self._analyze_text = analyze_text_use_case
        self._source_parsers: dict[InputMethod, SourceParser] = source_parsers or {}
        self._structured_srt_parser = structured_srt_parser
        self._media_repo = media_repo

    def start(self, source_id: int) -> None:
        """Validate source and mark as PROCESSING. Call before launching background task."""
        source = self._source_repo.get_by_id(source_id)
        if source is None:
            raise SourceNotFoundError(source_id)
        if source.status not in _ALLOWED_START_STATUSES:
            raise SourceAlreadyProcessedError(source_id)
        self._source_repo.update_status(source_id, SourceStatus.PROCESSING)

    def _notify_stage(
        self,
        source_id: int,
        stage: ProcessingStage,
        on_stage_commit: Callable[[], None] | None,
    ) -> None:
        logger.info(
            "process_source: stage transition (source_id=%d, stage=%s)",
            source_id, stage.value,
        )
        self._source_repo.update_status(
            source_id, SourceStatus.PROCESSING, processing_stage=stage,
        )
        if on_stage_commit:
            on_stage_commit()

    def execute(
        self,
        source_id: int,
        *,
        on_stage_commit: Callable[[], None] | None = None,
    ) -> None:
        """Run the full pipeline and save results. Call in background thread."""
        logger.info("process_source: execute start (source_id=%d)", source_id)
        source = self._source_repo.get_by_id(source_id)
        if source is None:
            raise SourceNotFoundError(source_id)

        # Stage 1: source-specific cleaning (subtitles/lyrics parsing)
        self._notify_stage(source_id, ProcessingStage.CLEANING_SOURCE, on_stage_commit)
        cefr_level = self._settings_repo.get("cefr_level", "B1") or "B1"

        parsed_srt: ParsedSrt | None = None

        if source.content_type == ContentType.VIDEO and self._structured_srt_parser:
            parsed_srt = self._structured_srt_parser.parse_structured(source.raw_text)
            raw_text = parsed_srt.text
        else:
            parser = self._source_parsers.get(source.input_method)
            raw_text = parser.parse(source.raw_text) if parser else source.raw_text

        # Stage 2: text analysis (cleaning + tokenization + filtering)
        self._notify_stage(source_id, ProcessingStage.ANALYZING_TEXT, on_stage_commit)
        request = AnalyzeTextRequest(
            raw_text=raw_text,
            user_level=cefr_level,
        )
        result = self._analyze_text.execute(request)

        known_pairs = self._known_word_repo.get_all_pairs()
        filtered = [c for c in result.candidates if (c.lemma, c.pos) not in known_pairs]

        if parsed_srt is not None:
            self._notify_stage(source_id, ProcessingStage.MAPPING_TIMECODES, on_stage_commit)

        # Map context fragments to timecodes if we have a parsed SRT
        timecode_map: dict[str, tuple[int, int]] = {}
        if parsed_srt is not None:
            for c in filtered:
                result_tc = find_timecodes(c.context_fragment, parsed_srt)
                if result_tc is not None:
                    timecode_map[c.context_fragment] = result_tc

        stored: list[StoredCandidate] = []
        for c in filtered:
            bd = dto_to_breakdown(c.cefr_breakdown) if c.cefr_breakdown else None
            stored.append(StoredCandidate(
                source_id=source_id,
                lemma=c.lemma,
                pos=c.pos,
                cefr_level=c.cefr_level,
                zipf_frequency=c.zipf_frequency,
                context_fragment=c.context_fragment,
                fragment_purity=c.fragment_purity,
                occurrences=c.occurrences,
                surface_form=c.surface_form,
                is_phrasal_verb=c.is_phrasal_verb,
                status=CandidateStatus.PENDING,
                cefr_breakdown=bd,
            ))
        created = self._candidate_repo.create_batch(stored)

        # Persist timecodes into candidate_media table if we have them
        if timecode_map and self._media_repo is not None:
            for sc in created:
                if sc.id is not None and sc.context_fragment in timecode_map:
                    start_ms, end_ms = timecode_map[sc.context_fragment]
                    self._media_repo.upsert(CandidateMedia(
                        candidate_id=sc.id,
                        screenshot_path=None,
                        audio_path=None,
                        start_ms=start_ms,
                        end_ms=end_ms,
                        status=EnrichmentStatus.IDLE,
                        error=None,
                        generated_at=None,
                    ))
        self._source_repo.update_status(
            source_id, SourceStatus.DONE, cleaned_text=result.cleaned_text,
        )
        logger.info(
            "process_source: done (source_id=%d, candidates_created=%d, "
            "with_timecodes=%d)",
            source_id, len(created), len(timecode_map),
        )
