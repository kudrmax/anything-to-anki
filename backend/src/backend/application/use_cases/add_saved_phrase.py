from __future__ import annotations

import contextlib
from typing import TYPE_CHECKING

from backend.application.utils.candidate_factory import CandidateFactory
from backend.application.utils.collected_phrases import CollectedPhrases
from backend.domain.entities.source import Source
from backend.domain.exceptions import ActionRefusedError, InvalidPhraseError
from backend.domain.value_objects.card_choice import Press
from backend.domain.value_objects.source_role import SourceRole

if TYPE_CHECKING:
    from backend.application.dto.source_dtos import CardDTO
    from backend.application.use_cases.decide_phrase import DecidePhraseUseCase
    from backend.application.utils.card_views import CardViews
    from backend.application.utils.phrase_reader import PhraseReader
    from backend.application.utils.review_status_updater import ReviewStatusUpdater
    from backend.domain.ports.candidate_repository import CandidateRepository
    from backend.domain.ports.cefr_classifier import CEFRClassifier
    from backend.domain.ports.frequency_provider import FrequencyProvider
    from backend.domain.ports.occurrence_repository import OccurrenceRepository
    from backend.domain.ports.source_repository import SourceRepository
    from backend.domain.ports.text_analyzer import TextAnalyzer
    from backend.domain.services.phrasal_verb_detector import PhrasalVerbDetector

SINGLE_OCCURRENCE = 1


class AddSavedPhraseUseCase:
    """Saves a phrase met anywhere, with the target the user picked in it.

    The phrase goes to the built-in "Saved phrases" source; a word new there is pressed
    Learn: the user chose it, there is nothing to review. That press goes by the press
    table, as any Learn: a word Known or learned in another source only shows that (Q4).
    """

    def __init__(
        self,
        source_repo: SourceRepository,
        candidate_repo: CandidateRepository,
        text_analyzer: TextAnalyzer,
        cefr_classifier: CEFRClassifier,
        frequency_provider: FrequencyProvider,
        phrasal_verb_detector: PhrasalVerbDetector,
        review_status: ReviewStatusUpdater,
        phrase_reader: PhraseReader,
        occurrence_repo: OccurrenceRepository,
        card_views: CardViews,
        decide_phrase: DecidePhraseUseCase,
    ) -> None:
        self._source_repo = source_repo
        self._decide_phrase = decide_phrase
        self._occurrences = occurrence_repo
        self._card_views = card_views
        self._collected = CollectedPhrases(candidate_repo, occurrence_repo)
        self._candidate_factory = CandidateFactory(
            text_analyzer=text_analyzer,
            cefr_classifier=cefr_classifier,
            frequency_provider=frequency_provider,
            phrasal_verb_detector=phrasal_verb_detector,
        )
        self._review_status = review_status
        self._phrase_reader = phrase_reader

    def execute(self, phrase: str, target_words: list[int]) -> CardDTO:
        """Answers with the card of the saved phrase."""
        text = " ".join(phrase.split())
        if not text:
            raise InvalidPhraseError("Phrase cannot be empty")
        read = self._phrase_reader.read_picked(text, target_words)

        source_id = self._saved_phrases_source_id()
        card = self._candidate_factory.build(
            source_id=source_id, phrase=read, occurrences=SINGLE_OCCURRENCE,
        )
        [collected] = self._collected.add(source_id, [card])
        if collected.new_word:
            self._learn(collected.phrase_id)
        self._review_status.refresh(source_id)
        return self._card_views.one(collected.phrase_id)

    def _learn(self, phrase_id: int) -> None:
        """Decided in another source, the card shows that decision instead."""
        with contextlib.suppress(ActionRefusedError):
            self._decide_phrase.press(phrase_id, Press.LEARN)

    def _saved_phrases_source_id(self) -> int:
        source = self._source_repo.get_first_by_role(SourceRole.SAVED_PHRASES)
        if source is None:
            source = self._source_repo.create(Source.saved_phrases())
        assert source.id is not None
        return source.id
