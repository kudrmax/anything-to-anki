from __future__ import annotations

import logging
import os
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from backend.application.utils.media_names import AUDIO_FILE, SCREENSHOT_FILE
from backend.domain.entities.candidate_media import CandidateMedia
from backend.domain.exceptions import (
    BadVideoFormatError,
    InvalidTimecodesError,
    PermanentMediaError,
)

if TYPE_CHECKING:
    from backend.application.utils.job_phrases import JobPhrases
    from backend.domain.ports.candidate_media_repository import CandidateMediaRepository
    from backend.domain.ports.media_extractor import MediaExtractor
    from backend.domain.ports.media_files import MediaFiles
    from backend.domain.ports.source_repository import SourceRepository
    from backend.domain.ports.video_path_resolver import VideoPathResolver
    from backend.domain.value_objects.phrase_ref import PhraseRef

logger = logging.getLogger(__name__)


class MediaExtractionUseCase:
    """Extracts screenshot and audio for one phrase.

    One-shot: called by worker per phrase. Permanent errors raise
    PermanentMediaError subclasses for the worker wrapper to catch.
    Transient errors (subprocess timeout, etc.) propagate for retry.
    A phrase a Rebuild changed or deleted meanwhile gets nothing.
    """

    def __init__(
        self,
        job_phrases: JobPhrases,
        media_repo: CandidateMediaRepository,
        source_repo: SourceRepository,
        media_extractor: MediaExtractor,
        media_files: MediaFiles,
        video_path_resolver: VideoPathResolver,
    ) -> None:
        self._job_phrases = job_phrases
        self._media_repo = media_repo
        self._source_repo = source_repo
        self._media_extractor = media_extractor
        self._media_files = media_files
        self._video_path_resolver = video_path_resolver

    def execute_one(self, phrase: PhraseRef) -> None:
        card = self._job_phrases.card(phrase)
        if card is None:
            return
        media = card.phrase.media
        if media is None or media.start_ms is None or media.end_ms is None:
            raise InvalidTimecodesError(f"Phrase {card.phrase_id} has no timecodes")

        source = self._source_repo.get_by_id(card.word.source_id)
        if source is None or source.id is None:
            raise PermanentMediaError(f"Source {card.word.source_id} not found")
        if source.video_path is None:
            raise BadVideoFormatError(f"Video missing for source {source.id}")
        resolved_video_path = self._video_path_resolver.resolve(
            source.video_path, source.format,
        )
        if not os.path.exists(resolved_video_path):
            raise BadVideoFormatError(f"Video missing for source {source.id}")

        start_ms = media.start_ms
        end_ms = media.end_ms
        screenshot = self._media_files.draft(source.id, card.phrase_id, SCREENSHOT_FILE)
        audio = self._media_files.draft(source.id, card.phrase_id, AUDIO_FILE)
        try:
            ts_ms = (start_ms + end_ms) // 2
            # Transient errors (subprocess.TimeoutExpired, OSError) propagate → worker retries
            self._media_extractor.extract_screenshot(resolved_video_path, ts_ms, screenshot.path)
            self._media_extractor.extract_audio(
                resolved_video_path, start_ms, end_ms, audio.path,
                audio_track_index=source.audio_track_index,
            )
            if not self._job_phrases.holds(card):
                return
            self._media_files.keep(screenshot)
            self._media_files.keep(audio)
        finally:
            self._media_files.discard(screenshot)
            self._media_files.discard(audio)
        self._media_repo.upsert_for_phrase(card.phrase_id, CandidateMedia(
            candidate_id=card.word_id,
            screenshot_path=screenshot.final_path,
            audio_path=audio.final_path,
            start_ms=start_ms,
            end_ms=end_ms,
            generated_at=datetime.now(tz=UTC),
        ))
        logger.info("MediaExtraction phrase %d: DONE", card.phrase_id)
