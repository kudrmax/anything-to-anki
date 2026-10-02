from __future__ import annotations

import json
from typing import TYPE_CHECKING

from backend.application.constants import (
    DEFAULT_USAGE_GROUP_ORDER,
    FREQUENT_WORD_THRESHOLD_SETTING,
    USAGE_GROUP_ORDER_SETTING,
)
from backend.domain.services import candidate_sorting
from backend.domain.value_objects.frequent_word_threshold import (
    DEFAULT_FREQUENT_WORD_THRESHOLD,
    FrequentWordThreshold,
)

if TYPE_CHECKING:
    from backend.domain.entities.stored_candidate import StoredCandidate
    from backend.domain.ports.settings_repository import SettingsRepository


class RelevanceSorter:
    """Sorts candidates by relevance using the user's settings."""

    def __init__(self, settings_repo: SettingsRepository) -> None:
        self._settings_repo = settings_repo

    def sort(self, candidates: list[StoredCandidate]) -> list[StoredCandidate]:
        return candidate_sorting.sort_by_relevance(
            candidates,
            usage_order=self._usage_order(),
            frequent_threshold=read_frequent_word_threshold(self._settings_repo),
        )

    def _usage_order(self) -> list[str]:
        raw = self._settings_repo.get(USAGE_GROUP_ORDER_SETTING)
        return json.loads(raw) if raw else DEFAULT_USAGE_GROUP_ORDER


def read_frequent_word_threshold(settings_repo: SettingsRepository) -> FrequentWordThreshold:
    raw = settings_repo.get(FREQUENT_WORD_THRESHOLD_SETTING)
    if not isinstance(raw, str):
        return DEFAULT_FREQUENT_WORD_THRESHOLD
    try:
        return FrequentWordThreshold.from_key(raw)
    except ValueError:
        return DEFAULT_FREQUENT_WORD_THRESHOLD
