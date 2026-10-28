from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from backend.domain.entities.token_data import TokenData
    from backend.domain.ports.stop_words import StopWords
    from backend.domain.value_objects.cefr_level import CEFRLevel

# Parts of speech a word is learned as; a stop word used as one of them is a word of its own.
CONTENT_POS: frozenset[str] = frozenset({"NOUN", "VERB", "ADJ"})
# Verbs that build tenses, whatever part of speech the tagger gives them.
AUXILIARY_VERBS: frozenset[str] = frozenset({"be", "have", "do"})


class CandidateFilter:
    """Filters tokens to identify relevant learning candidates."""

    def is_relevant_token(self, token: TokenData) -> bool:
        """Check if a token is worth considering as a learning candidate.

        Excludes: punctuation, stop words, proper nouns, non-alphabetic tokens.
        """
        if token.is_punct:
            return False
        if token.is_stop:
            return False
        if token.is_propn:
            return False
        return token.is_alpha

    def is_function_word(self, lemma: str, pos: str, stop_words: StopWords) -> bool:
        """An auxiliary verb, or a stop word not used as a noun, verb or adjective. Judged by
        the word, not its form: "na" of "gonna" is "to", "wo" of "won't" is "will"."""
        if lemma in AUXILIARY_VERBS:
            return True
        return pos not in CONTENT_POS and stop_words.contains(lemma)

    def is_learned_at_user_level(self, cefr: CEFRLevel, user_level: CEFRLevel) -> bool:
        """Check if a word's CEFR level is the user's level or above."""
        return cefr.is_learned_at(user_level)
