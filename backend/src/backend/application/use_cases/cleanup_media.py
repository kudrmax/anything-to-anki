from __future__ import annotations

import logging
import os
from typing import TYPE_CHECKING

from backend.application.dto.media_dtos import CleanupMediaKind

if TYPE_CHECKING:
    from backend.domain.ports.candidate_repository import CandidateRepository

logger = logging.getLogger(__name__)


class CleanupMediaUseCase:
    """Deletes media files on disk and clears their DB paths for a source."""

    def __init__(
        self,
        candidate_repo: CandidateRepository,
        media_root: str,
    ) -> None:
        self._candidate_repo = candidate_repo
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
            if clear_screenshot and c.screenshot_path:
                try:
                    if os.path.exists(c.screenshot_path):
                        os.remove(c.screenshot_path)
                        removed_shot += 1
                except OSError:
                    logger.exception("Failed to remove screenshot %s", c.screenshot_path)
            if clear_audio and c.audio_path:
                try:
                    if os.path.exists(c.audio_path):
                        os.remove(c.audio_path)
                        removed_audio += 1
                except OSError:
                    logger.exception("Failed to remove audio %s", c.audio_path)

            # Clear DB paths for this candidate
            self._candidate_repo.clear_media_path(
                c.id,
                clear_screenshot=clear_screenshot,
                clear_audio=clear_audio,
            )

        # If all media for this source is cleared, remove the directory too
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
