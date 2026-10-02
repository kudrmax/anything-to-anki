from __future__ import annotations

from typing import TYPE_CHECKING

from backend.domain.services.candidate_filter import CandidateFilter

if TYPE_CHECKING:
    from collections.abc import Iterable

    from backend.domain.entities.token_data import TokenData
    from backend.domain.ports.cefr_classifier import CEFRClassifier
    from backend.domain.ports.frequency_provider import FrequencyProvider
    from backend.domain.value_objects.cefr_level import CEFRLevel

MISSING_FROM_DICTIONARY_ZIPF: float = 0.0
# A restored "hope" must be a common word: "visite", "develope" are typos at ~2.
MIN_RESTORED_WORD_ZIPF: float = 3.0
# "pants" is used far more than "pant": a plural-only noun, not a plural.
PLURAL_ONLY_MARGIN_ZIPF: float = 0.5
INFLECTED_VERB_TAGS: frozenset[str] = frozenset({"VBG", "VBD", "VBN"})
VERB_ENDINGS: tuple[str, ...] = ("ing", "ed")
PLURAL_NOUN_TAG = "NNS"
VOWELS = frozenset("aeiou")
NEVER_DOUBLED_CONSONANTS = frozenset("wxy")
SILENT_E = "e"


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
        frequent_zipf: float | None,
    ) -> None:
        self._cefr_classifier = cefr_classifier
        self._frequency_provider = frequency_provider
        self._user_level = user_level
        self._known_lemmas = known_lemmas
        self._frequent_zipf = frequent_zipf
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
        """The token's dictionary form, with the lemmatizer's mistakes fixed:

        - a non-word lemma falls back to the word as written ("syphili");
        - a lost silent "e" is restored ("hoping" → "hop" → "hope");
        - a plural-only noun keeps its "s" ("pants" → "pant" → "pants").
        """
        lemma = token.lemma.lower()
        surface = token.text.lower()
        if (
            self.zipf(lemma) <= MISSING_FROM_DICTIONARY_ZIPF
            and self.zipf(surface) > MISSING_FROM_DICTIONARY_ZIPF
        ):
            return surface
        if token.tag in INFLECTED_VERB_TAGS and self._lost_silent_e(lemma, surface):
            return lemma + SILENT_E
        if (
            token.tag == PLURAL_NOUN_TAG
            and self.zipf(surface) - self.zipf(lemma) >= PLURAL_ONLY_MARGIN_ZIPF
        ):
            return surface
        return lemma

    def _lost_silent_e(self, lemma: str, surface: str) -> bool:
        """English doubles the last consonant of a short stem before -ing/-ed
        (hop → hopping). An undoubled form of such a stem ("hoping") can only
        come from a stem with a silent "e" ("hope")."""
        if not any(surface == lemma + ending for ending in VERB_ENDINGS):
            return False
        if not _ends_consonant_vowel_consonant(lemma):
            return False
        return self.zipf(lemma + SILENT_E) >= MIN_RESTORED_WORD_ZIPF

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
                and not self._is_frequent(lemma)
                and self._filter.is_above_user_level(
                    self._cefr_classifier.classify(lemma, token.tag), self._user_level,
                )
            )
        return self._unknown_cache[key]

    def _is_frequent(self, lemma: str) -> bool:
        return self._frequent_zipf is not None and self.zipf(lemma) >= self._frequent_zipf


def _ends_consonant_vowel_consonant(word: str) -> bool:
    if len(word) < 3:
        return False
    first, vowel, last = word[-3], word[-2], word[-1]
    return (
        first not in VOWELS
        and vowel in VOWELS
        and last not in VOWELS
        and last not in NEVER_DOUBLED_CONSONANTS
    )
