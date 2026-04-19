from __future__ import annotations

import logging
import os
import urllib.request
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from backend.domain.entities.candidate_pronunciation import CandidatePronunciation
from backend.domain.value_objects.enrichment_status import EnrichmentStatus

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from backend.domain.ports.candidate_pronunciation_repository import (
        CandidatePronunciationRepository,
    )
    from backend.domain.ports.candidate_repository import CandidateRepository
    from backend.domain.ports.pronunciation_source import PronunciationSource


def download_file(url: str, dest: str) -> None:
    """Download a file from URL to local path."""
    urllib.request.urlretrieve(url, dest)  # noqa: S310 — URLs come from trusted Cambridge JSONL


class DownloadPronunciationUseCase:
    """Downloads pronunciation audio for a single candidate."""

    def __init__(
        self,
        candidate_repo: CandidateRepository,
        pronunciation_repo: CandidatePronunciationRepository,
        pronunciation_source: PronunciationSource,
        media_root: str,
    ) -> None:
        self._candidate_repo = candidate_repo
        self._pronunciation_repo = pronunciation_repo
        self._pronunciation_source = pronunciation_source
        self._media_root = media_root

    def execute_one(self, candidate_id: int) -> None:
        candidate = self._candidate_repo.get_by_id(candidate_id)
        if candidate is None:
            logger.warning("download_pronunciation: candidate %d not found", candidate_id)
            return

        # Check if still RUNNING (may have been cancelled)
        current = self._pronunciation_repo.get_by_candidate_id(candidate_id)
        if current is None or current.status != EnrichmentStatus.RUNNING:
            logger.info(
                "download_pronunciation: skipped %d (status=%s)",
                candidate_id,
                current.status.value if current else "no row",
            )
            return

        us_url, uk_url = self._pronunciation_source.get_audio_urls(candidate.lemma)

        if us_url is None and uk_url is None:
            self._pronunciation_repo.upsert(CandidatePronunciation(
                candidate_id=candidate_id,
                us_audio_path=None,
                uk_audio_path=None,
                status=EnrichmentStatus.DONE,
                error=None,
                generated_at=datetime.now(tz=UTC),
            ))
            logger.info(
                "download_pronunciation: no audio for %s (candidate %d)",
                candidate.lemma,
                candidate_id,
            )
            return

        out_dir = os.path.join(self._media_root, str(candidate.source_id))
        os.makedirs(out_dir, exist_ok=True)

        us_path: str | None = None
        uk_path: str | None = None

        if us_url:
            us_path = os.path.join(out_dir, f"{candidate_id}_pron_us.mp3")
            download_file(us_url, us_path)

        if uk_url:
            uk_path = os.path.join(out_dir, f"{candidate_id}_pron_uk.mp3")
            download_file(uk_url, uk_path)

        # Re-check status before final upsert (may have been cancelled during download)
        current = self._pronunciation_repo.get_by_candidate_id(candidate_id)
        if current is None or current.status != EnrichmentStatus.RUNNING:
            logger.info("download_pronunciation: cancelled during download for %d", candidate_id)
            return

        self._pronunciation_repo.upsert(CandidatePronunciation(
            candidate_id=candidate_id,
            us_audio_path=us_path,
            uk_audio_path=uk_path,
            status=EnrichmentStatus.DONE,
            error=None,
            generated_at=datetime.now(tz=UTC),
        ))
        logger.info(
            "download_pronunciation: done for %s (candidate %d, us=%s, uk=%s)",
            candidate.lemma,
            candidate_id,
            bool(us_path),
            bool(uk_path),
        )
