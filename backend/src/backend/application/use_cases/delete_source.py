from __future__ import annotations

import logging
import os
import shutil
from typing import TYPE_CHECKING

from backend.domain.exceptions import SourceIsProcessingError, SourceNotFoundError
from backend.domain.value_objects.source_status import SourceStatus

if TYPE_CHECKING:
    from backend.domain.ports.candidate_repository import CandidateRepository
    from backend.domain.ports.source_repository import SourceRepository

logger = logging.getLogger(__name__)


class DeleteSourceUseCase:
    """Deletes a source, its candidates, and its media directory."""

    def __init__(
        self,
        source_repo: SourceRepository,
        candidate_repo: CandidateRepository,
        media_root: str,
    ) -> None:
        self._source_repo = source_repo
        self._candidate_repo = candidate_repo
        self._media_root = media_root

    def execute(self, source_id: int) -> None:
        source = self._source_repo.get_by_id(source_id)
        if source is None:
            raise SourceNotFoundError(source_id)
        if source.status == SourceStatus.PROCESSING:
            raise SourceIsProcessingError(source_id)

        # Clean up media directory before removing DB rows.
        media_dir = os.path.join(self._media_root, str(source_id))
        if os.path.isdir(media_dir):
            shutil.rmtree(media_dir, ignore_errors=True)
            logger.info("Deleted media directory %s", media_dir)

        self._candidate_repo.delete_by_source(source_id)
        self._source_repo.delete(source_id)
