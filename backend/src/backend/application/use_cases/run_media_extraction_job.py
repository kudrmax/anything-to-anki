from __future__ import annotations

import os
from typing import TYPE_CHECKING

from backend.domain.value_objects.media_extraction_job_status import MediaExtractionJobStatus

if TYPE_CHECKING:
    from backend.domain.ports.candidate_repository import CandidateRepository
    from backend.domain.ports.media_extractor import MediaExtractor
    from backend.domain.ports.media_extraction_job_repository import MediaExtractionJobRepository
    from backend.domain.ports.source_repository import SourceRepository


class RunMediaExtractionJobUseCase:
    """Executes a media extraction job: screenshot + audio per candidate."""

    def __init__(
        self,
        job_repo: MediaExtractionJobRepository,
        candidate_repo: CandidateRepository,
        source_repo: SourceRepository,
        media_extractor: MediaExtractor,
        media_root: str,
    ) -> None:
        self._job_repo = job_repo
        self._candidate_repo = candidate_repo
        self._source_repo = source_repo
        self._media_extractor = media_extractor
        self._media_root = media_root

    def execute(self, job_id: int) -> None:
        job = self._job_repo.get_by_id(job_id)
        if job is None:
            return

        job.status = MediaExtractionJobStatus.RUNNING
        self._job_repo.update(job)

        for candidate_id in job.candidate_ids:
            candidate = self._candidate_repo.get_by_id(candidate_id)
            if candidate is None or candidate.media_start_ms is None:
                job.skipped_candidates += 1
                self._job_repo.update(job)
                continue

            source = self._source_repo.get_by_id(candidate.source_id)
            if source is None or source.video_path is None or not os.path.exists(source.video_path):
                job.skipped_candidates += 1
                self._job_repo.update(job)
                continue

            out_dir = os.path.join(self._media_root, str(candidate.source_id))
            os.makedirs(out_dir, exist_ok=True)
            screenshot_path = os.path.join(out_dir, f"{candidate_id}_screenshot.jpg")
            audio_path = os.path.join(out_dir, f"{candidate_id}_audio.mp3")

            try:
                start_ms = candidate.media_start_ms
                end_ms = candidate.media_end_ms
                assert start_ms is not None and end_ms is not None  # guaranteed by StartMediaExtractionUseCase filter
                ts_ms = (start_ms + end_ms) // 2
                self._media_extractor.extract_screenshot(source.video_path, ts_ms, screenshot_path)
                self._media_extractor.extract_audio(
                    source.video_path,
                    start_ms,
                    end_ms,
                    audio_path,
                )
                self._candidate_repo.update_media_paths(
                    candidate_id,
                    screenshot_path=screenshot_path,
                    audio_path=audio_path,
                )
                job.processed_candidates += 1
            except Exception:  # noqa: BLE001
                job.failed_candidates += 1

            self._job_repo.update(job)

        job.status = MediaExtractionJobStatus.DONE
        self._job_repo.update(job)
