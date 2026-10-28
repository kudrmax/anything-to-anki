from __future__ import annotations

from typing import TYPE_CHECKING

from backend.application.constants import FREQUENT_WORD_THRESHOLD_SETTING
from backend.domain.value_objects.frequent_word_threshold import (
    DEFAULT_FREQUENT_WORD_THRESHOLD,
    FrequentWordThreshold,
)

if TYPE_CHECKING:
    from backend.domain.ports.settings_repository import SettingsRepository


class FrequentWordThresholdResolver:
    """The user's frequent word threshold."""

    def __init__(self, settings_repo: SettingsRepository) -> None:
        self._settings_repo = settings_repo

    def resolve(self) -> FrequentWordThreshold:
        raw = self._settings_repo.get(FREQUENT_WORD_THRESHOLD_SETTING)
        if not isinstance(raw, str):
            return DEFAULT_FREQUENT_WORD_THRESHOLD
        return self.resolve_for(raw)

    def resolve_for(self, key: str) -> FrequentWordThreshold:
        """The threshold the settings would give if they held `key`."""
        try:
            return FrequentWordThreshold.from_key(key)
        except ValueError:
            return DEFAULT_FREQUENT_WORD_THRESHOLD
