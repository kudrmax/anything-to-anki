from __future__ import annotations

import json
from typing import TYPE_CHECKING

from backend.application.constants import (
    DEFAULT_USAGE_GROUP_ORDER,
    USAGE_GROUP_ORDER_SETTING,
)
from backend.domain.services import candidate_sorting
from backend.domain.value_objects.candidate_sort_order import CandidateSortOrder

if TYPE_CHECKING:
    from backend.application.utils.frequent_word_threshold_resolver import (
        FrequentWordThresholdResolver,
    )
    from backend.domain.entities.source import Source
    from backend.domain.entities.stored_candidate import StoredCandidate
    from backend.domain.ports.settings_repository import SettingsRepository


class CandidateSorter:
    """Sorts candidates in the order the user picked, using the user's settings."""

    def __init__(
        self,
        settings_repo: SettingsRepository,
        threshold_resolver: FrequentWordThresholdResolver,
    ) -> None:
        self._settings_repo = settings_repo
        self._threshold_resolver = threshold_resolver

    def sort(
        self,
        candidates: list[StoredCandidate],
        source: Source,
        order: CandidateSortOrder = CandidateSortOrder.RELEVANCE,
    ) -> list[StoredCandidate]:
        if order == CandidateSortOrder.CHRONOLOGICAL:
            return candidate_sorting.sort_chronologically(
                candidates, source_text=source.cleaned_text or source.raw_text,
            )
        if order == CandidateSortOrder.KEY_WORDS:
            return candidate_sorting.sort_by_key_words(
                candidates, frequent_threshold=self._threshold_resolver.resolve(),
            )
        return self.sort_by_relevance(candidates)

    def sort_by_relevance(self, candidates: list[StoredCandidate]) -> list[StoredCandidate]:
        return candidate_sorting.sort_by_relevance(
            candidates,
            usage_order=self._usage_order(),
            frequent_threshold=self._threshold_resolver.resolve(),
        )

    def _usage_order(self) -> list[str]:
        raw = self._settings_repo.get(USAGE_GROUP_ORDER_SETTING)
        return json.loads(raw) if raw else DEFAULT_USAGE_GROUP_ORDER
