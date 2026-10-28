from __future__ import annotations

from typing import TYPE_CHECKING

from backend.application.constants import FREQUENT_WORD_THRESHOLD_SETTING
from backend.application.utils.saved_level import saved_level
from backend.domain.services.frequency_threshold_calibrator import (
    FrequencyThresholdCalibrator,
)
from backend.domain.value_objects.frequent_word_threshold import (
    DEFAULT_FREQUENT_WORD_THRESHOLD,
    FrequentWordThreshold,
    auto_start_zipf,
    step_index,
)

if TYPE_CHECKING:
    from backend.domain.ports.settings_repository import SettingsRepository
    from backend.domain.ports.word_decision_repository import WordDecisionRepository
    from backend.domain.value_objects.cefr_level import CEFRLevel


class FrequentWordThresholdResolver:
    """The user's frequent word threshold; Auto starts at their level and is calibrated on
    their decisions."""

    def __init__(
        self,
        settings_repo: SettingsRepository,
        decision_repo: WordDecisionRepository,
    ) -> None:
        self._settings_repo = settings_repo
        self._decision_repo = decision_repo
        self._calibrator = FrequencyThresholdCalibrator()

    def resolve(self) -> FrequentWordThreshold:
        return self._checked(self._configured(), saved_level(self._settings_repo))

    def resolve_for(self, key: str, level: CEFRLevel | None = None) -> FrequentWordThreshold:
        """The threshold the settings would give if they held `key` and `level`; the saved
        level without one."""
        return self._checked(_parsed(key), level or saved_level(self._settings_repo))

    def _checked(
        self, configured: FrequentWordThreshold, level: CEFRLevel,
    ) -> FrequentWordThreshold:
        threshold = self._resolved(configured, level)
        step_index(threshold.zipf)
        return threshold

    def _resolved(
        self, threshold: FrequentWordThreshold, level: CEFRLevel,
    ) -> FrequentWordThreshold:
        if not threshold.is_auto:
            return threshold
        return threshold.calibrated(self._auto_zipf(level))

    def auto_zipf(self) -> float | None:
        """What Auto gives at the saved level; None — no threshold."""
        return self._auto_zipf(saved_level(self._settings_repo))

    def _auto_zipf(self, level: CEFRLevel) -> float | None:
        return self._calibrator.calibrate(
            self._decision_repo.list_all(), auto_start_zipf(level),
        )

    def _configured(self) -> FrequentWordThreshold:
        raw = self._settings_repo.get(FREQUENT_WORD_THRESHOLD_SETTING)
        if not isinstance(raw, str):
            return DEFAULT_FREQUENT_WORD_THRESHOLD
        return _parsed(raw)


def _parsed(key: str) -> FrequentWordThreshold:
    try:
        return FrequentWordThreshold.from_key(key)
    except ValueError:
        return DEFAULT_FREQUENT_WORD_THRESHOLD
