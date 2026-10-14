from __future__ import annotations

import logging
import os
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from backend.application.utils.media_names import AUDIO_FILE, SCREENSHOT_FILE, phrase_file
from backend.domain.entities.candidate_media import CandidateMedia
from backend.domain.exceptions import PhraseChangedError
from backend.domain.services.document_time import time_of

if TYPE_CHECKING:
    from backend.application.utils.requested_cards import RequestedCards
    from backend.domain.ports.candidate_media_repository import CandidateMediaRepository
    from backend.domain.ports.document_repository import DocumentRepository
    from backend.domain.ports.media_extractor import MediaExtractor
    from backend.domain.ports.occurrence_repository import OccurrenceRepository
    from backend.domain.ports.source_repository import SourceRepository
    from backend.domain.ports.video_path_resolver import VideoPathResolver

logger = logging.getLogger(__name__)


class RegeneratePhraseMediaUseCase:
    """Regenerates screenshot and audio for one phrase, taking the time from the document
    lines the phrase takes now."""

    def __init__(
        self,
        cards: RequestedCards,
        occurrence_repo: OccurrenceRepository,
        media_repo: CandidateMediaRepository,
        source_repo: SourceRepository,
        document_repo: DocumentRepository,
        media_extractor: MediaExtractor,
        media_root: str,
        video_path_resolver: VideoPathResolver,
    ) -> None:
        self._cards = cards
        self._occurrence_repo = occurrence_repo
        self._media_repo = media_repo
        self._source_repo = source_repo
        self._document_repo = document_repo
        self._media_extractor = media_extractor
        self._media_root = media_root
        self._video_path_resolver = video_path_resolver

    def execute(self, phrase_id: int) -> None:
        card = self._cards.card(phrase_id)
        source_id = card.word.source_id
        source = self._source_repo.get_by_id(source_id)
        if source is None or source.id is None:
            raise ValueError(f"Source {source_id} not found")
        if not source.has_video:
            raise ValueError(f"Source {source.id} is not a video")
        if source.video_path is None:
            raise ValueError(f"Video file missing for source {source.id}")
        resolved_video_path = self._video_path_resolver.resolve(
            source.video_path, source.format,
        )
        if not os.path.exists(resolved_video_path):
            raise ValueError(f"Video file missing for source {source.id}")

        document = self._document_repo.get(source_id)
        position = card.phrase.phrase_position
        timecodes = time_of(document, position) if document and position else None
        if timecodes is None:
            raise ValueError("Fragment not found in subtitles")
        start_ms, end_ms = timecodes

        screenshot_path = phrase_file(self._media_root, source.id, phrase_id, SCREENSHOT_FILE)
        audio_path = phrase_file(self._media_root, source.id, phrase_id, AUDIO_FILE)

        midpoint_ms = (start_ms + end_ms) // 2
        self._media_extractor.extract_screenshot(resolved_video_path, midpoint_ms, screenshot_path)
        self._media_extractor.extract_audio(
            resolved_video_path,
            start_ms,
            end_ms,
            audio_path,
            audio_track_index=source.audio_track_index,
        )

        if not self._occurrence_repo.holds_revision(phrase_id, card.phrase.revision):
            raise PhraseChangedError(phrase_id)
        self._media_repo.upsert_for_phrase(phrase_id, CandidateMedia(
            candidate_id=card.word_id,
            screenshot_path=screenshot_path,
            audio_path=audio_path,
            start_ms=start_ms,
            end_ms=end_ms,
            generated_at=datetime.now(tz=UTC),
        ))

        logger.info(
            "Regenerated media for phrase %d: timecodes=(%d,%d) midpoint=%d",
            phrase_id, start_ms, end_ms, midpoint_ms,
        )
