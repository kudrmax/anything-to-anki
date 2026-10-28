"""Real candidate sorting over a mocked or fake settings repository.

Use cases take a ``CandidateSorter``; tests keep configuring sorting through
the settings repository, with no word decisions unless they pass some. The user
knows no words and is at B1; frequent words follow the same threshold as sorting.
"""
from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import MagicMock

from backend.application.utils.candidate_sorter import CandidateSorter
from backend.application.utils.frequent_word_threshold_resolver import (
    FrequentWordThresholdResolver,
)
from backend.application.utils.section_stamper import SectionStamper
from backend.domain.value_objects.cefr_level import CEFRLevel
from backend.domain.value_objects.user_knowledge import UserKnowledge
from backend.domain.value_objects.vocabulary import EMPTY_VOCABULARY

if TYPE_CHECKING:
    from backend.domain.entities.word_decision import WordDecision
    from backend.domain.ports.settings_repository import SettingsRepository


def no_settings() -> MagicMock:
    """A settings repository with nothing saved: every setting is its default."""
    repo = MagicMock()
    repo.get.side_effect = lambda _key, default=None: default
    return repo


def threshold_resolver(
    settings_repo: SettingsRepository,
    decisions: list[WordDecision] | None = None,
) -> FrequentWordThresholdResolver:
    decision_repo = MagicMock()
    decision_repo.list_all.return_value = decisions or []
    return FrequentWordThresholdResolver(settings_repo, decision_repo)


def candidate_sorter(settings_repo: SettingsRepository) -> CandidateSorter:
    resolver = threshold_resolver(settings_repo)
    knowledge = MagicMock()
    knowledge.current.side_effect = lambda: UserKnowledge(
        EMPTY_VOCABULARY, CEFRLevel.B1, resolver.resolve().zipf,
    )
    return CandidateSorter(settings_repo, resolver, knowledge)


def section_stamper(settings_repo: SettingsRepository) -> SectionStamper:
    """A real stamper over the same knowledge as `candidate_sorter`."""
    resolver = threshold_resolver(settings_repo)
    knowledge = MagicMock()
    knowledge.current.side_effect = lambda: UserKnowledge(
        EMPTY_VOCABULARY, CEFRLevel.B1, resolver.resolve().zipf,
    )
    return SectionStamper(knowledge, resolver)
