from __future__ import annotations

import logging
import os
import shutil
from typing import TYPE_CHECKING

from backend.domain.exceptions import SourceNotFoundError
from backend.domain.services.source_actions import ensure_deletable

if TYPE_CHECKING:
    from backend.domain.ports.anki_sync_repository import AnkiSyncRepository
    from backend.domain.ports.candidate_repository import CandidateRepository
    from backend.domain.ports.source_operation_lock import SourceOperationLock
    from backend.domain.ports.source_repository import SourceRepository
    from backend.domain.ports.unit_of_work import UnitOfWork

logger = logging.getLogger(__name__)


class DeleteSourceUseCase:
    """Deletes a source, its candidates, and its media directory."""

    def __init__(
        self,
        source_repo: SourceRepository,
        candidate_repo: CandidateRepository,
        anki_sync: AnkiSyncRepository,
        lock: SourceOperationLock,
        media_root: str,
        unit_of_work: UnitOfWork,
    ) -> None:
        self._unit_of_work = unit_of_work
        self._source_repo = source_repo
        self._candidate_repo = candidate_repo
        self._anki_sync = anki_sync
        self._lock = lock
        self._media_root = media_root

    def execute(self, source_id: int) -> None:
        """The rows go in a write; the media directory after it is committed, so no file
        is deleted under the write lock or for a delete that was rolled back."""
        with self._unit_of_work.write():
            self._delete(source_id)
        media_dir = os.path.join(self._media_root, str(source_id))
        if os.path.isdir(media_dir):
            shutil.rmtree(media_dir, ignore_errors=True)
            logger.info("Deleted media directory %s", media_dir)

    def _delete(self, source_id: int) -> None:
        source = self._source_repo.get_by_id(source_id)
        if source is None:
            raise SourceNotFoundError(source_id)
        ensure_deletable(source, self._lock.held(source_id))
        self._anki_sync.orphan_source(source_id)
        self._candidate_repo.delete_by_source(source_id)
        self._source_repo.delete(source_id)
