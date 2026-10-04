from __future__ import annotations

import dataclasses
from typing import TYPE_CHECKING

from backend.application.dto.source_dtos import StoredCandidateDTO, stored_candidate_to_dto
from backend.application.utils.candidate_factory import CandidateFactory
from backend.domain.entities.source import Source
from backend.domain.exceptions import InvalidPhraseError
from backend.domain.services.phrase_target import normalize_target, phrase_contains_target
from backend.domain.value_objects.candidate_status import CandidateStatus
from backend.domain.value_objects.content_type import ContentType

if TYPE_CHECKING:
    from backend.application.utils.review_status_updater import ReviewStatusUpdater
    from backend.domain.ports.candidate_repository import CandidateRepository
    from backend.domain.ports.cefr_classifier import CEFRClassifier
    from backend.domain.ports.frequency_provider import FrequencyProvider
    from backend.domain.ports.source_repository import SourceRepository
    from backend.domain.ports.text_analyzer import TextAnalyzer
    from backend.domain.services.phrasal_verb_detector import PhrasalVerbDetector

SINGLE_OCCURRENCE = 1


class AddSavedPhraseUseCase:
    """Saves a phrase met anywhere, with the target the user picked in it.

    The phrase goes to the built-in "Saved phrases" source as a candidate
    already marked to learn: the user chose it, there is nothing to review.
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
    ) -> None:
        self._source_repo = source_repo
        self._candidate_repo = candidate_repo
        self._candidate_factory = CandidateFactory(
            text_analyzer=text_analyzer,
            cefr_classifier=cefr_classifier,
            frequency_provider=frequency_provider,
            phrasal_verb_detector=phrasal_verb_detector,
        )
        self._review_status = review_status

    def execute(self, phrase: str, target: str) -> StoredCandidateDTO:
        phrase = " ".join(phrase.split())
        target = normalize_target(target)
        if not phrase:
            raise InvalidPhraseError("Phrase cannot be empty")
        if not phrase_contains_target(phrase, target):
            raise InvalidPhraseError("Pick the target among the words of the phrase")

        source_id = self._saved_phrases_source_id()
        candidate = self._candidate_factory.build(
            source_id=source_id,
            surface_form=target,
            context_fragment=phrase,
            occurrences=SINGLE_OCCURRENCE,
        )
        learned = dataclasses.replace(candidate, status=CandidateStatus.LEARN)
        saved = self._candidate_repo.create_batch([learned])[0]
        self._review_status.refresh(source_id)
        return stored_candidate_to_dto(saved)

    def _saved_phrases_source_id(self) -> int:
        source = self._source_repo.get_first_by_content_type(ContentType.PHRASES)
        if source is None:
            source = self._source_repo.create(Source.saved_phrases())
        assert source.id is not None
        return source.id
