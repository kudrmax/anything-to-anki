from __future__ import annotations

from typing import TYPE_CHECKING

from backend.application.constants import FREQUENT_WORD_THRESHOLD_SETTING
from backend.domain.services.frequency_threshold_calibrator import (
    FrequencyThresholdCalibrator,
)
from backend.domain.value_objects.frequent_word_threshold import (
    DEFAULT_FREQUENT_WORD_THRESHOLD,
    FrequentWordThreshold,
)

if TYPE_CHECKING:
    from backend.domain.ports.settings_repository import SettingsRepository
    from backend.domain.ports.word_decision_repository import WordDecisionRepository


class FrequentWordThresholdResolver:
    """The user's frequent word threshold; Auto is calibrated on their decisions."""

    def __init__(
        self,
        settings_repo: SettingsRepository,
        decision_repo: WordDecisionRepository,
    ) -> None:
        self._settings_repo = settings_repo
        self._decision_repo = decision_repo
        self._calibrator = FrequencyThresholdCalibrator()

    def resolve(self) -> FrequentWordThreshold:
        threshold = self._configured()
        if not threshold.is_auto:
            return threshold
        return threshold.calibrated(self.auto_zipf())

    def auto_zipf(self) -> float:
        return self._calibrator.calibrate(self._decision_repo.list_all())

    def _configured(self) -> FrequentWordThreshold:
        raw = self._settings_repo.get(FREQUENT_WORD_THRESHOLD_SETTING)
        if not isinstance(raw, str):
            return DEFAULT_FREQUENT_WORD_THRESHOLD
        try:
            return FrequentWordThreshold.from_key(raw)
        except ValueError:
            return DEFAULT_FREQUENT_WORD_THRESHOLD
