"""Real candidate sorting over a mocked or fake settings repository.

Use cases take a ``CandidateSorter``; tests keep configuring sorting through
the settings repository, with no word decisions unless they pass some.
"""
from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import MagicMock

from backend.application.utils.candidate_sorter import CandidateSorter
from backend.application.utils.frequent_word_threshold_resolver import (
    FrequentWordThresholdResolver,
)

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


def candidate_sorter(settings_repo: SettingsRepository) -> CandidateSorter:
    return CandidateSorter(settings_repo, threshold_resolver(settings_repo))
