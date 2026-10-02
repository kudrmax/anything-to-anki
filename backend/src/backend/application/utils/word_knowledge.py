from __future__ import annotations

from typing import TYPE_CHECKING

from backend.domain.services.candidate_filter import CandidateFilter

if TYPE_CHECKING:
    from collections.abc import Iterable

    from backend.domain.entities.token_data import TokenData
    from backend.domain.ports.cefr_classifier import CEFRClassifier
    from backend.domain.ports.frequency_provider import FrequencyProvider
    from backend.domain.value_objects.cefr_level import CEFRLevel
    from backend.domain.value_objects.frequent_word_threshold import FrequentWordThreshold

MISSING_FROM_DICTIONARY_ZIPF: float = 0.0


class WordKnowledge:
    """What the user probably knows, for one analysed text.

    A word is probably unknown when it is above the user's CEFR level, is not
    in the user's known words and is not frequent enough to be known anyway.
    Lookups are cached: one text asks about the same words many times.
    """

    def __init__(
        self,
        cefr_classifier: CEFRClassifier,
        frequency_provider: FrequencyProvider,
        user_level: CEFRLevel,
        known_lemmas: frozenset[str],
        frequent_threshold: FrequentWordThreshold,
    ) -> None:
        self._cefr_classifier = cefr_classifier
        self._frequency_provider = frequency_provider
        self._user_level = user_level
        self._known_lemmas = known_lemmas
        self._frequent_threshold = frequent_threshold
        self._filter = CandidateFilter()
        self._zipf_cache: dict[str, float] = {}
        self._unknown_cache: dict[tuple[str, str], bool] = {}

    def is_known(self, lemma: str) -> bool:
        return lemma in self._known_lemmas

    def zipf(self, lemma: str) -> float:
        if lemma not in self._zipf_cache:
            self._zipf_cache[lemma] = self._frequency_provider.get_zipf_value(lemma)
        return self._zipf_cache[lemma]

    def lemma_of(self, token: TokenData) -> str:
        """The token's dictionary form, or the word as written when the
        lemmatizer produced a non-word ("syphilis" → "syphili")."""
        lemma = token.lemma.lower()
        surface = token.text.lower()
        if (
            self.zipf(lemma) <= MISSING_FROM_DICTIONARY_ZIPF
            and self.zipf(surface) > MISSING_FROM_DICTIONARY_ZIPF
        ):
            return surface
        return lemma

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
        if not self._filter.is_relevant_token(token):
            return False
        lemma = self.lemma_of(token)
        key = (lemma, token.tag)
        if key not in self._unknown_cache:
            self._unknown_cache[key] = (
                not self.is_known(lemma)
                and not self._frequent_threshold.covers(self.zipf(lemma))
                and self._filter.is_above_user_level(
                    self._cefr_classifier.classify(lemma, token.tag), self._user_level,
                )
            )
        return self._unknown_cache[key]
