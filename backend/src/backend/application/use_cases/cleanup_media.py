from __future__ import annotations

import logging
import os
from typing import TYPE_CHECKING

from backend.application.dto.media_dtos import CleanupMediaKind

if TYPE_CHECKING:
    from backend.domain.entities.stored_candidate import StoredCandidate
    from backend.domain.ports.candidate_meaning_image_repository import (
        CandidateMeaningImageRepository,
    )
    from backend.domain.ports.candidate_media_repository import CandidateMediaRepository
    from backend.domain.ports.candidate_repository import CandidateRepository

logger = logging.getLogger(__name__)


class CleanupMediaUseCase:
    """Deletes media files on disk and clears their DB paths for a source.

    Images are both the video frames and the meaning images of the cards.
    """

    def __init__(
        self,
        candidate_repo: CandidateRepository,
        media_repo: CandidateMediaRepository,
        image_repo: CandidateMeaningImageRepository,
        media_root: str,
    ) -> None:
        self._candidate_repo = candidate_repo
        self._media_repo = media_repo
        self._image_repo = image_repo
        self._media_root = media_root

    def execute(self, source_id: int, kind: CleanupMediaKind) -> None:
        clear_screenshot = kind in (CleanupMediaKind.ALL, CleanupMediaKind.IMAGES)
        clear_audio = kind in (CleanupMediaKind.ALL, CleanupMediaKind.AUDIO)

        candidates = self._candidate_repo.get_by_source(source_id)
        removed_shot = 0
        removed_audio = 0

        for c in candidates:
            if c.id is None:
                continue
            if clear_screenshot and c.meaning_image is not None:
                removed_shot += self._remove_meaning_image(c)
            if c.media is None:
                continue
            if clear_screenshot and c.media.screenshot_path:
                try:
                    if os.path.exists(c.media.screenshot_path):
                        os.remove(c.media.screenshot_path)
                        removed_shot += 1
                except OSError:
                    logger.exception("Failed to remove screenshot %s", c.media.screenshot_path)
            if clear_audio and c.media.audio_path:
                try:
                    if os.path.exists(c.media.audio_path):
                        os.remove(c.media.audio_path)
                        removed_audio += 1
                except OSError:
                    logger.exception("Failed to remove audio %s", c.media.audio_path)

            self._media_repo.clear_paths(
                c.id,
                clear_screenshot=clear_screenshot,
                clear_audio=clear_audio,
            )

        source_dir = os.path.join(self._media_root, str(source_id))
        if kind == CleanupMediaKind.ALL and os.path.isdir(source_dir):
            try:
                if not os.listdir(source_dir):
                    os.rmdir(source_dir)
            except OSError:
                pass

        logger.info(
            "CleanupMedia source=%d kind=%s: removed %d screenshots, %d audio files",
            source_id, kind.value, removed_shot, removed_audio,
        )

    def _remove_meaning_image(self, candidate: StoredCandidate) -> int:
        assert candidate.id is not None and candidate.meaning_image is not None
        path = candidate.meaning_image.image_path
        removed = 0
        try:
            if os.path.exists(path):
                os.remove(path)
                removed = 1
        except OSError:
            logger.exception("Failed to remove meaning image %s", path)
        self._image_repo.delete_by_candidate_id(candidate.id)
        return removed
