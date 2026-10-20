from __future__ import annotations

from unittest.mock import MagicMock

from backend.application.utils.section_stamper import SectionStamper
from backend.domain.value_objects.cefr_level import CEFRLevel
from backend.domain.value_objects.frequent_word_threshold import FrequentWordThreshold
from backend.domain.value_objects.user_knowledge import UserKnowledge
from backend.domain.value_objects.vocabulary import EMPTY_VOCABULARY


def test_the_stamper_reads_knowledge_and_threshold_once_per_rule() -> None:
    knowledge = MagicMock()
    knowledge.current.return_value = UserKnowledge(EMPTY_VOCABULARY, CEFRLevel.B1, None)
    resolver = MagicMock()
    resolver.resolve.return_value = FrequentWordThreshold.from_key("off")

    rule = SectionStamper(knowledge, resolver).rule()

    knowledge.current.assert_called_once_with()
    resolver.resolve.assert_called_once_with()
    assert rule.frequent_threshold is resolver.resolve.return_value
