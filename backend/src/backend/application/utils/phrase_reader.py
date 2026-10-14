from __future__ import annotations

from typing import TYPE_CHECKING

from backend.application.utils.word_facts import WordFacts
from backend.domain.exceptions import TargetNotInPhraseError
from backend.domain.services.phrase_building import build_phrase, target_by_lemma, words_of
from backend.domain.value_objects.phrase import Phrase

if TYPE_CHECKING:
    from collections.abc import Sequence

    from backend.domain.entities.token_data import TokenData
    from backend.domain.ports.cefr_classifier import CEFRClassifier
    from backend.domain.ports.frequency_provider import FrequencyProvider
    from backend.domain.ports.text_analyzer import TextAnalyzer
    from backend.domain.services.phrase_building import TokenFacts


class PhraseReader:
    """The only place a text becomes a card phrase: its words, what they are, its target."""

    def __init__(
        self,
        text_analyzer: TextAnalyzer,
        cefr_classifier: CEFRClassifier,
        frequency_provider: FrequencyProvider,
    ) -> None:
        self._text_analyzer = text_analyzer
        self._cefr_classifier = cefr_classifier
        self._frequency_provider = frequency_provider

    def read(self, text: str, target_spans: Sequence[tuple[int, int]]) -> Phrase:
        """The target is the words the given characters of the text touch."""
        return build_phrase(text, self._facts(text), target_spans)

    def read_for(self, text: str, lemma: str) -> Phrase:
        """A new text of a card: its target is found again by the card's lemma."""
        words = words_of(text, self._facts(text))
        target = target_by_lemma(words, text, lemma)
        if not target:
            raise TargetNotInPhraseError()
        return Phrase(text=text, words=words, target=target)

    def facts(self, tokens: Sequence[TokenData], offset: int = 0) -> list[TokenFacts]:
        """Facts of tokens already parsed elsewhere, e.g. a whole document."""
        facts = WordFacts(self._cefr_classifier, self._frequency_provider)
        return [facts.facts(token, offset) for token in tokens]

    def _facts(self, text: str) -> list[TokenFacts]:
        return self.facts(self._text_analyzer.analyze(text))
