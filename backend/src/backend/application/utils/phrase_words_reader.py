from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from backend.application.utils.word_knowledge import WordKnowledge
from backend.domain.value_objects.cefr_level import CEFRLevel
from backend.domain.value_objects.vocabulary import EMPTY_VOCABULARY

if TYPE_CHECKING:
    from collections.abc import Iterable

    from backend.application.utils.frequent_word_threshold_resolver import (
        FrequentWordThresholdResolver,
    )
    from backend.domain.entities.stored_candidate import StoredCandidate
    from backend.domain.ports.candidate_repository import CandidateRepository
    from backend.domain.ports.cefr_classifier import CEFRClassifier
    from backend.domain.ports.frequency_provider import FrequencyProvider
    from backend.domain.ports.settings_repository import SettingsRepository
    from backend.domain.ports.text_analyzer import TextAnalyzer
    from backend.domain.value_objects.phrase_words import PhraseWords

logger = logging.getLogger(__name__)

DEFAULT_CEFR_LEVEL = "B1"


class PhraseWordsReader:
    """Keeps a card's phrase words in step with the phrase the card shows.

    The phrase changes in many ways: AI polish, its revert, a hand edit, a new
    boundary, an example taken as the phrase. Whatever changed it, the words
    are read again the next time the cards are looked at.
    """

    def __init__(
        self,
        candidate_repo: CandidateRepository,
        text_analyzer: TextAnalyzer,
        cefr_classifier: CEFRClassifier,
        frequency_provider: FrequencyProvider,
        settings_repo: SettingsRepository,
        threshold_resolver: FrequentWordThresholdResolver,
    ) -> None:
        self._candidate_repo = candidate_repo
        self._text_analyzer = text_analyzer
        self._cefr_classifier = cefr_classifier
        self._frequency_provider = frequency_provider
        self._settings_repo = settings_repo
        self._threshold_resolver = threshold_resolver

    def refresh(self, candidates: list[StoredCandidate]) -> None:
        """Read the words of every card whose phrase changed since they were read."""
        stale = [
            c for c in candidates
            if c.id is not None
            and (c.phrase_words is None or not c.phrase_words.is_of(c.card_phrase))
        ]
        if not stale:
            return
        knowledge = self._knowledge()
        for candidate in stale:
            assert candidate.id is not None
            candidate.phrase_words = self._read(candidate, knowledge)
            self._candidate_repo.set_phrase_words(candidate.id, candidate.phrase_words)
        logger.info("phrase_words_reader: read %d phrases", len(stale))

    def lemmas_at(self, phrase: str, spans: Iterable[tuple[int, int]]) -> list[str]:
        """The words of the phrase that the character spans touch, as lemmas."""
        wanted = list(spans)
        knowledge = self._knowledge()
        lemmas: list[str] = []
        for token in self._text_analyzer.analyze(phrase):
            touched = any(
                token.char_start < end and start < token.char_end for start, end in wanted
            )
            lemma = knowledge.lemma_of(token)
            if touched and token.is_alpha and lemma not in lemmas:
                lemmas.append(lemma)
        return lemmas

    def _read(self, candidate: StoredCandidate, knowledge: WordKnowledge) -> PhraseWords:
        phrase = candidate.card_phrase
        tokens = self._text_analyzer.analyze(phrase)
        target = _target_words(candidate)
        excluded = frozenset(
            token.index for token in tokens
            if token.text.lower() in target or knowledge.lemma_of(token) in target
        )
        return knowledge.phrase_words(range(len(tokens)), tokens, excluded, phrase)

    def _knowledge(self) -> WordKnowledge:
        level = self._settings_repo.get("cefr_level", DEFAULT_CEFR_LEVEL) or DEFAULT_CEFR_LEVEL
        return WordKnowledge(
            cefr_classifier=self._cefr_classifier,
            frequency_provider=self._frequency_provider,
            user_level=CEFRLevel.from_str(level),
            vocabulary=EMPTY_VOCABULARY,
            frequent_zipf=self._threshold_resolver.resolve().zipf,
        )


def _target_words(candidate: StoredCandidate) -> frozenset[str]:
    """Every word of the target, as a lemma and as written: "give up", "gave up"."""
    return frozenset(candidate.lemma.lower().split()) | frozenset(
        (candidate.surface_form or "").lower().split(),
    )
