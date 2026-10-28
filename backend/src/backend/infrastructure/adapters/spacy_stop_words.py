from __future__ import annotations

from spacy.lang.en.stop_words import STOP_WORDS

from backend.domain.ports.stop_words import StopWords


class SpacyStopWords(StopWords):
    """spaCy's English stop words, the same list that marks a token as a stop word."""

    def contains(self, lemma: str) -> bool:
        return lemma.lower() in STOP_WORDS
