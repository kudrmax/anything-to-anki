from __future__ import annotations

from typing import TYPE_CHECKING

from backend.domain.services.candidate_filter import CandidateFilter
from backend.domain.services.phrase_building import TokenFacts

if TYPE_CHECKING:
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


class WordFacts:
    """What the dictionaries say about the words of a text: dictionary form, CEFR level,
    frequency, whether a word can be new at all. Nothing about the user.

    Lookups are cached: one text asks about the same words many times.
    """

    def __init__(
        self, cefr_classifier: CEFRClassifier, frequency_provider: FrequencyProvider,
    ) -> None:
        self._cefr_classifier = cefr_classifier
        self._frequency_provider = frequency_provider
        self._filter = CandidateFilter()
        self._zipf_cache: dict[str, float] = {}
        self._level_cache: dict[tuple[str, str], CEFRLevel] = {}

    def zipf(self, lemma: str) -> float:
        if lemma not in self._zipf_cache:
            self._zipf_cache[lemma] = self._frequency_provider.get_zipf_value(lemma)
        return self._zipf_cache[lemma]

    def level(self, lemma: str, tag: str) -> CEFRLevel:
        key = (lemma, tag)
        if key not in self._level_cache:
            self._level_cache[key] = self._cefr_classifier.classify(lemma, tag)
        return self._level_cache[key]

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

    def facts(self, token: TokenData, offset: int = 0) -> TokenFacts:
        """What a phrase keeps of a token; `offset` is where the phrase starts in the text."""
        lemma = self.lemma_of(token)
        return TokenFacts(
            start=token.char_start - offset,
            end=token.char_end - offset,
            lemma=lemma,
            level=self.level(lemma, token.tag),
            zipf=self.zipf(lemma),
            content=self._filter.is_relevant_token(token),
            alpha=token.is_alpha,
        )

    def _lost_silent_e(self, lemma: str, surface: str) -> bool:
        """English doubles the last consonant of a short stem before -ing/-ed
        (hop → hopping). An undoubled form of such a stem ("hoping") can only
        come from a stem with a silent "e" ("hope")."""
        if not any(surface == lemma + ending for ending in VERB_ENDINGS):
            return False
        if not _ends_consonant_vowel_consonant(lemma):
            return False
        return self.zipf(lemma + SILENT_E) >= MIN_RESTORED_WORD_ZIPF


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
