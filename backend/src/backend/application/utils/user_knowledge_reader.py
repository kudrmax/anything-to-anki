from __future__ import annotations

from typing import TYPE_CHECKING

from backend.domain.value_objects.cefr_level import CEFRLevel
from backend.domain.value_objects.user_knowledge import KnowledgeBase, UserKnowledge

if TYPE_CHECKING:
    from backend.application.utils.frequent_word_threshold_resolver import (
        FrequentWordThresholdResolver,
    )
    from backend.application.utils.user_vocabulary import UserVocabulary
    from backend.domain.ports.settings_repository import SettingsRepository

DEFAULT_CEFR_LEVEL = "B1"


class UserKnowledgeReader:
    """What decides right now whether a word is new: the user's words, level and threshold."""

    def __init__(
        self,
        vocabulary: UserVocabulary,
        settings_repo: SettingsRepository,
        threshold_resolver: FrequentWordThresholdResolver,
    ) -> None:
        self._vocabulary = vocabulary
        self._settings_repo = settings_repo
        self._threshold_resolver = threshold_resolver

    def current(self) -> UserKnowledge:
        return UserKnowledge(
            vocabulary=self._vocabulary.snapshot(),
            user_level=self._level(),
            frequent_zipf=self._threshold_resolver.resolve().zipf,
        )

    def base(self) -> KnowledgeBase:
        """What the user knows apart from the frequent word threshold."""
        return KnowledgeBase(vocabulary=self._vocabulary.snapshot(), user_level=self._level())

    def _level(self) -> CEFRLevel:
        level = self._settings_repo.get("cefr_level", DEFAULT_CEFR_LEVEL) or DEFAULT_CEFR_LEVEL
        return CEFRLevel.from_str(level)
