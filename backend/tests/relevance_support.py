"""Real relevance sorting over a mocked or fake settings repository.

Use cases take a ``RelevanceSorter``; tests keep configuring sorting through
the settings repository, with no word decisions unless they pass some.
"""
from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import MagicMock

from backend.application.utils.frequent_word_threshold_resolver import (
    FrequentWordThresholdResolver,
)
from backend.application.utils.relevance_sorter import RelevanceSorter

if TYPE_CHECKING:
    from backend.domain.entities.word_decision import WordDecision
    from backend.domain.ports.settings_repository import SettingsRepository


def threshold_resolver(
    settings_repo: SettingsRepository,
    decisions: list[WordDecision] | None = None,
) -> FrequentWordThresholdResolver:
    decision_repo = MagicMock()
    decision_repo.list_all.return_value = decisions or []
    return FrequentWordThresholdResolver(settings_repo, decision_repo)


def relevance_sorter(settings_repo: SettingsRepository) -> RelevanceSorter:
    return RelevanceSorter(settings_repo, threshold_resolver(settings_repo))
