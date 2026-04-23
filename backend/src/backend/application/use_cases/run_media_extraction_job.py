from __future__ import annotations

import logging
import os
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from backend.domain.entities.candidate_media import CandidateMedia
from backend.domain.exceptions import (
    BadVideoFormatError,
    InvalidTimecodesError,
    PermanentMediaError,
)

if TYPE_CHECKING:
    from backend.domain.ports.candidate_media_repository import CandidateMediaRepository
    from backend.domain.ports.candidate_repository import CandidateRepository
    from backend.domain.ports.media_extractor import MediaExtractor
    from backend.domain.ports.source_repository import SourceRepository
    from backend.domain.ports.video_path_resolver import VideoPathResolver

logger = logging.getLogger(__name__)


class MediaExtractionUseCase:
    """Extracts screenshot and audio for a single candidate.

    One-shot: called by worker per candidate. Permanent errors raise
    PermanentMediaError subclasses for the worker wrapper to catch.
    Transient errors (subprocess timeout, etc.) propagate for retry.
    """

    def __init__(
        self,
        candidate_repo: CandidateRepository,
        media_repo: CandidateMediaRepository,
        source_repo: SourceRepository,
        media_extractor: MediaExtractor,
        media_root: str,
        video_path_resolver: VideoPathResolver,
    ) -> None:
        self._candidate_repo = candidate_repo
        self._media_repo = media_repo
        self._source_repo = source_repo
        self._media_extractor = media_extractor
        self._media_root = media_root
        self._video_path_resolver = video_path_resolver

    def execute_one(self, candidate_id: int) -> None:
        candidate = self._candidate_repo.get_by_id(candidate_id)
        if candidate is None:
            raise PermanentMediaError(f"Candidate {candidate_id} not found")
        media = candidate.media
        if media is None or media.start_ms is None or media.end_ms is None:
            raise InvalidTimecodesError(f"Candidate {candidate_id} has no timecodes")

        source = self._source_repo.get_by_id(candidate.source_id)
        if source is None:
            raise PermanentMediaError(f"Source {candidate.source_id} not found")
        if source.video_path is None:
            raise BadVideoFormatError(f"Video missing for source {source.id}")
        resolved_video_path = self._video_path_resolver.resolve(
            source.video_path, source.input_method,
        )
        if not os.path.exists(resolved_video_path):
            raise BadVideoFormatError(f"Video missing for source {source.id}")

        start_ms = media.start_ms
        end_ms = media.end_ms

        out_dir = os.path.join(self._media_root, str(source.id))
        os.makedirs(out_dir, exist_ok=True)
        screenshot_path = os.path.join(out_dir, f"{candidate_id}_screenshot.webp")
        audio_path = os.path.join(out_dir, f"{candidate_id}_audio.m4a")

        ts_ms = (start_ms + end_ms) // 2
        # Transient errors (subprocess.TimeoutExpired, OSError) propagate → worker retries
        self._media_extractor.extract_screenshot(resolved_video_path, ts_ms, screenshot_path)
        self._media_extractor.extract_audio(
            resolved_video_path, start_ms, end_ms, audio_path,
            audio_track_index=source.audio_track_index,
        )

        self._media_repo.upsert(CandidateMedia(
            candidate_id=candidate_id,
            screenshot_path=screenshot_path,
            audio_path=audio_path,
            start_ms=start_ms,
            end_ms=end_ms,
            generated_at=datetime.now(tz=UTC),
        ))
        logger.info("MediaExtraction candidate %d: DONE", candidate_id)
