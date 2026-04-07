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
from backend.domain.value_objects.enrichment_status import EnrichmentStatus

if TYPE_CHECKING:
    from backend.domain.ports.candidate_media_repository import CandidateMediaRepository
    from backend.domain.ports.candidate_repository import CandidateRepository
    from backend.domain.ports.media_extractor import MediaExtractor
    from backend.domain.ports.source_repository import SourceRepository

logger = logging.getLogger(__name__)


class MediaExtractionUseCase:
    """Extracts screenshot and audio for a single candidate.

    One-shot: called by worker per candidate. Writes status transitions
    (RUNNING → DONE) to candidate_media. Permanent errors raise
    PermanentMediaError subclasses for the worker wrapper to catch.
    Transient errors (subprocess timeout, etc.) propagate for ARQ retry.
    """

    def __init__(
        self,
        candidate_repo: CandidateRepository,
        media_repo: CandidateMediaRepository,
        source_repo: SourceRepository,
        media_extractor: MediaExtractor,
        media_root: str,
    ) -> None:
        self._candidate_repo = candidate_repo
        self._media_repo = media_repo
        self._source_repo = source_repo
        self._media_extractor = media_extractor
        self._media_root = media_root

    def execute_one(self, candidate_id: int) -> None:
        # Note: mark_running is done by the worker wrapper in a separate
        # committed session — so even if this use case rolls back on failure,
        # the user still sees that we tried.

        candidate = self._candidate_repo.get_by_id(candidate_id)
        if candidate is None:
            raise PermanentMediaError(f"Candidate {candidate_id} not found")
        media = candidate.media
        if media is None or media.start_ms is None or media.end_ms is None:
            raise InvalidTimecodesError(f"Candidate {candidate_id} has no timecodes")

        source = self._source_repo.get_by_id(candidate.source_id)
        if source is None:
            raise PermanentMediaError(f"Source {candidate.source_id} not found")
        if source.video_path is None or not os.path.exists(source.video_path):
            raise BadVideoFormatError(f"Video missing for source {source.id}")

        start_ms = media.start_ms
        end_ms = media.end_ms

        out_dir = os.path.join(self._media_root, str(source.id))
        os.makedirs(out_dir, exist_ok=True)
        screenshot_path = os.path.join(out_dir, f"{candidate_id}_screenshot.webp")
        audio_path = os.path.join(out_dir, f"{candidate_id}_audio.m4a")

        ts_ms = (start_ms + end_ms) // 2
        # Transient errors (subprocess.TimeoutExpired, OSError) propagate → ARQ retries
        self._media_extractor.extract_screenshot(source.video_path, ts_ms, screenshot_path)
        self._media_extractor.extract_audio(
            source.video_path, start_ms, end_ms, audio_path,
            audio_track_index=source.audio_track_index,
        )

        # Pre-upsert guard: check current status. If the user clicked Cancel
        # while we were running ffmpeg, the row is now FAILED ('cancelled by
        # user'). Skip writing to avoid overwriting it.
        current = self._media_repo.get_by_candidate_id(candidate_id)
        if current is None or current.status != EnrichmentStatus.RUNNING:
            logger.info(
                "MediaExtraction candidate %d: skipped (cancelled by user)",
                candidate_id,
            )
            return

        self._media_repo.upsert(CandidateMedia(
            candidate_id=candidate_id,
            screenshot_path=screenshot_path,
            audio_path=audio_path,
            start_ms=start_ms,
            end_ms=end_ms,
            status=EnrichmentStatus.DONE,
            error=None,
            generated_at=datetime.now(tz=UTC),
        ))
        logger.info("MediaExtraction candidate %d: DONE", candidate_id)
