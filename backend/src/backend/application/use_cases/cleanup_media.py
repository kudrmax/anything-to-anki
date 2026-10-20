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
    from backend.domain.ports.occurrence_repository import OccurrenceRepository
    from backend.domain.ports.unit_of_work import UnitOfWork

logger = logging.getLogger(__name__)


class CleanupMediaUseCase:
    """Deletes media files on disk and clears their DB paths for a source.

    The video frames and clips are those of every phrase of the source, shown or not;
    images are also the pictures of its words.
    """

    def __init__(
        self,
        candidate_repo: CandidateRepository,
        occurrence_repo: OccurrenceRepository,
        media_repo: CandidateMediaRepository,
        image_repo: CandidateMeaningImageRepository,
        media_root: str,
        unit_of_work: UnitOfWork,
    ) -> None:
        self._unit_of_work = unit_of_work
        self._candidate_repo = candidate_repo
        self._occurrence_repo = occurrence_repo
        self._media_repo = media_repo
        self._image_repo = image_repo
        self._media_root = media_root

    def execute(self, source_id: int, kind: CleanupMediaKind) -> None:
        with self._unit_of_work.write():
            self._clean(source_id, kind)

    def _clean(self, source_id: int, kind: CleanupMediaKind) -> None:
        clear_screenshot = kind in (CleanupMediaKind.ALL, CleanupMediaKind.IMAGES)
        clear_audio = kind in (CleanupMediaKind.ALL, CleanupMediaKind.AUDIO)
        removed_shot = 0
        removed_audio = 0

        if clear_screenshot:
            for word in self._candidate_repo.get_by_source(source_id):
                if word.id is not None and word.meaning_image is not None:
                    removed_shot += self._remove_meaning_image(word)

        for occurrence in self._occurrence_repo.by_source(source_id):
            media = occurrence.media
            if occurrence.id is None or media is None:
                continue
            if clear_screenshot and media.screenshot_path:
                removed_shot += _remove(media.screenshot_path)
            if clear_audio and media.audio_path:
                removed_audio += _remove(media.audio_path)
            self._media_repo.clear_phrase_paths(
                occurrence.id, clear_screenshot=clear_screenshot, clear_audio=clear_audio,
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

    def _remove_meaning_image(self, word: StoredCandidate) -> int:
        assert word.id is not None and word.meaning_image is not None
        removed = _remove(word.meaning_image.image_path)
        self._image_repo.delete_by_candidate_id(word.id)
        return removed


def _remove(path: str) -> int:
    """1 when the file was there and is gone now."""
    try:
        if os.path.exists(path):
            os.remove(path)
            return 1
    except OSError:
        logger.exception("Failed to remove media file %s", path)
    return 0
