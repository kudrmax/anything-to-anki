from __future__ import annotations

import logging
import os
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from backend.domain.entities.candidate_media import CandidateMedia
from backend.domain.value_objects.enrichment_status import EnrichmentStatus
from backend.domain.value_objects.media_extraction_job_status import MediaExtractionJobStatus

if TYPE_CHECKING:
    from backend.domain.ports.candidate_media_repository import CandidateMediaRepository
    from backend.domain.ports.candidate_repository import CandidateRepository
    from backend.domain.ports.media_extraction_job_repository import MediaExtractionJobRepository
    from backend.domain.ports.media_extractor import MediaExtractor
    from backend.domain.ports.source_repository import SourceRepository

logger = logging.getLogger(__name__)


class RunMediaExtractionJobUseCase:
    """Executes a media extraction job: screenshot + audio per candidate."""

    def __init__(
        self,
        job_repo: MediaExtractionJobRepository,
        candidate_repo: CandidateRepository,
        source_repo: SourceRepository,
        media_extractor: MediaExtractor,
        media_root: str,
        media_repo: CandidateMediaRepository,
    ) -> None:
        self._job_repo = job_repo
        self._candidate_repo = candidate_repo
        self._source_repo = source_repo
        self._media_extractor = media_extractor
        self._media_root = media_root
        self._media_repo = media_repo

    def execute(self, job_id: int) -> None:
        job = self._job_repo.get_by_id(job_id)
        if job is None:
            logger.warning("MediaExtractionJob %d not found", job_id)
            return

        logger.info(
            "MediaExtractionJob %d starting: source_id=%s total=%d",
            job_id, job.source_id, job.total_candidates,
        )
        job.status = MediaExtractionJobStatus.RUNNING
        self._job_repo.update(job)

        for candidate_id in job.candidate_ids:
            candidate = self._candidate_repo.get_by_id(candidate_id)
            if candidate is None or candidate.media is None or candidate.media.start_ms is None:
                logger.info(
                    "MediaExtractionJob %d: skipping candidate %d (no timecodes)",
                    job_id, candidate_id,
                )
                job.skipped_candidates += 1
                self._job_repo.update(job)
                continue

            source = self._source_repo.get_by_id(candidate.source_id)
            if (
                source is None
                or source.video_path is None
                or not os.path.exists(source.video_path)
            ):
                logger.warning(
                    "MediaExtractionJob %d: skipping candidate %d (video file missing)",
                    job_id, candidate_id,
                )
                job.skipped_candidates += 1
                self._job_repo.update(job)
                continue

            out_dir = os.path.join(self._media_root, str(candidate.source_id))
            os.makedirs(out_dir, exist_ok=True)
            screenshot_path = os.path.join(out_dir, f"{candidate_id}_screenshot.webp")
            audio_path = os.path.join(out_dir, f"{candidate_id}_audio.m4a")

            try:
                start_ms = candidate.media.start_ms
                end_ms = candidate.media.end_ms
                assert start_ms is not None and end_ms is not None
                ts_ms = (start_ms + end_ms) // 2
                self._media_extractor.extract_screenshot(source.video_path, ts_ms, screenshot_path)
                self._media_extractor.extract_audio(
                    source.video_path,
                    start_ms,
                    end_ms,
                    audio_path,
                    audio_track_index=source.audio_track_index,
                )
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
                job.processed_candidates += 1
                logger.info(
                    "MediaExtractionJob %d: candidate %d done (%d/%d)",
                    job_id, candidate_id, job.processed_candidates, job.total_candidates,
                )
            except Exception:
                logger.exception(
                    "MediaExtractionJob %d: candidate %d failed",
                    job_id, candidate_id,
                )
                job.failed_candidates += 1

            self._job_repo.update(job)

        job.status = MediaExtractionJobStatus.DONE
        self._job_repo.update(job)
        logger.info(
            "MediaExtractionJob %d finished: processed=%d failed=%d skipped=%d",
            job_id, job.processed_candidates, job.failed_candidates, job.skipped_candidates,
        )
