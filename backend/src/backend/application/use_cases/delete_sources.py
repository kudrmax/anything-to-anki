from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from backend.application.dto.collection_dtos import DeletedSourcesDTO
from backend.domain.exceptions import (
    PermanentSourceError,
    SourceIsProcessingError,
    SourceNotFoundError,
)

if TYPE_CHECKING:
    from collections.abc import Sequence

    from backend.application.use_cases.delete_source import DeleteSourceUseCase

logger = logging.getLogger(__name__)


class DeleteSourcesUseCase:
    """Deletes the chosen sources; the ones that can't go (processing, built-in) are reported.

    Each source is deleted in a write of its own and its media go right after: a failure
    later in the batch leaves the sources already deleted deleted, as their files are."""

    def __init__(self, delete_source: DeleteSourceUseCase) -> None:
        self._delete_source = delete_source

    def execute(self, source_ids: Sequence[int]) -> DeletedSourcesDTO:
        deleted: list[int] = []
        skipped: list[int] = []
        for source_id in source_ids:
            try:
                self._delete_source.execute(source_id)
            except (SourceNotFoundError, SourceIsProcessingError, PermanentSourceError) as e:
                logger.info("Skipped deleting source %d: %s", source_id, e)
                skipped.append(source_id)
                continue
            deleted.append(source_id)
        return DeletedSourcesDTO(deleted=deleted, skipped=skipped)
