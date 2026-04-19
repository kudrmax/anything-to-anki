from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING

from backend.application.constants import DEFAULT_USAGE_GROUP_ORDER

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from backend.domain.ports.candidate_pronunciation_repository import (
        CandidatePronunciationRepository,
    )
    from backend.domain.ports.candidate_repository import CandidateRepository
    from backend.domain.ports.settings_repository import SettingsRepository


class EnqueuePronunciationDownloadUseCase:
    """Finds eligible candidates, marks them QUEUED, returns their IDs for arq enqueue."""

    def __init__(
        self,
        pronunciation_repo: CandidatePronunciationRepository,
        candidate_repo: CandidateRepository,
        settings_repo: SettingsRepository,
    ) -> None:
        self._pronunciation_repo = pronunciation_repo
        self._candidate_repo = candidate_repo
        self._settings_repo = settings_repo

    def execute(self, source_id: int) -> list[int]:
        from backend.domain.services.candidate_sorting import sort_by_relevance

        unsorted_ids = self._pronunciation_repo.get_eligible_candidate_ids(source_id)
        if not unsorted_ids:
            return []

        candidates = self._candidate_repo.get_by_ids(unsorted_ids)
        raw = self._settings_repo.get("usage_group_order")
        usage_order: list[str] = json.loads(raw) if raw else DEFAULT_USAGE_GROUP_ORDER
        sorted_candidates = sort_by_relevance(candidates, usage_order=usage_order)

        eligible_ids = [c.id for c in sorted_candidates if c.id is not None]
        if not eligible_ids:
            return []

        self._pronunciation_repo.mark_queued_bulk(eligible_ids)
        logger.info(
            "enqueue_pronunciation_download: queued (source_id=%d, count=%d)",
            source_id,
            len(eligible_ids),
        )
        return eligible_ids
