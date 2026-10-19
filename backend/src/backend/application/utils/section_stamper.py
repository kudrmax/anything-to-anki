from __future__ import annotations

from typing import TYPE_CHECKING

from backend.domain.services.candidate_sections import SectionRule

if TYPE_CHECKING:
    from backend.application.utils.frequent_word_threshold_resolver import (
        FrequentWordThresholdResolver,
    )
    from backend.application.utils.user_knowledge_reader import UserKnowledgeReader
    from backend.domain.services.candidate_sections import WordFacts
    from backend.domain.value_objects.candidate_section import CandidateSection
    from backend.domain.value_objects.phrase import Phrase


class SectionStamper:
    """The section a phrase earns from what the user knows right now."""

    def __init__(
        self,
        knowledge: UserKnowledgeReader,
        threshold_resolver: FrequentWordThresholdResolver,
    ) -> None:
        self._knowledge = knowledge
        self._threshold_resolver = threshold_resolver

    def rule(self) -> SectionRule:
        """Reads knowledge and threshold once, for stamping many phrases."""
        return SectionRule(
            knowledge=self._knowledge.current(),
            frequent_threshold=self._threshold_resolver.resolve(),
        )

    def earned(self, phrase: Phrase, word: WordFacts) -> CandidateSection:
        return self.rule().earned(phrase, word)
