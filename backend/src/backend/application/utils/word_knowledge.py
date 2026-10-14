from __future__ import annotations

from typing import TYPE_CHECKING

from backend.application.utils.word_facts import WordFacts
from backend.domain.services.phrase_building import words_of
from backend.domain.value_objects.user_knowledge import UserKnowledge

if TYPE_CHECKING:
    from collections.abc import Iterable

    from backend.domain.entities.token_data import TokenData
    from backend.domain.ports.cefr_classifier import CEFRClassifier
    from backend.domain.ports.frequency_provider import FrequencyProvider
    from backend.domain.value_objects.cefr_level import CEFRLevel
    from backend.domain.value_objects.vocabulary import Vocabulary


class WordKnowledge:
    """What the user probably knows, for one analysed text: the dictionaries' facts of its
    words judged by what the user knows now (see UserKnowledge.is_new)."""

    def __init__(
        self,
        cefr_classifier: CEFRClassifier,
        frequency_provider: FrequencyProvider,
        user_level: CEFRLevel,
        vocabulary: Vocabulary,
        frequent_zipf: float | None,
    ) -> None:
        self.facts = WordFacts(cefr_classifier, frequency_provider)
        self._user = UserKnowledge(
            vocabulary=vocabulary, user_level=user_level, frequent_zipf=frequent_zipf,
        )

    def is_known(self, lemma: str) -> bool:
        return self._user.vocabulary.is_known(lemma)

    def zipf(self, lemma: str) -> float:
        return self.facts.zipf(lemma)

    def lemma_of(self, token: TokenData) -> str:
        return self.facts.lemma_of(token)

    def count_unknowns(
        self,
        indices: Iterable[int],
        tokens: list[TokenData],
        excluded: frozenset[int],
    ) -> int:
        return sum(
            1 for idx in indices
            if idx not in excluded and self.is_probably_unknown(tokens[idx])
        )

    def is_probably_unknown(self, token: TokenData) -> bool:
        if not token.is_alpha:
            return False
        words = words_of(token.text, [self.facts.facts(token, token.char_start)])
        return bool(words) and self._user.is_new(words[0])
