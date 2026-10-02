from __future__ import annotations

from typing import TYPE_CHECKING

from backend.application.dto.source_dtos import StoredCandidateDTO, stored_candidate_to_dto
from backend.application.utils.candidate_factory import CandidateFactory
from backend.domain.exceptions import SourceNotFoundError

if TYPE_CHECKING:
    from backend.application.utils.review_status_updater import ReviewStatusUpdater
    from backend.domain.ports.candidate_repository import CandidateRepository
    from backend.domain.ports.cefr_classifier import CEFRClassifier
    from backend.domain.ports.frequency_provider import FrequencyProvider
    from backend.domain.ports.source_repository import SourceRepository
    from backend.domain.ports.text_analyzer import TextAnalyzer
    from backend.domain.services.phrasal_verb_detector import PhrasalVerbDetector


class AddManualCandidateUseCase:
    """Manually adds a word candidate selected by the user during review.

    Runs the same enrichment pipeline as automatic processing (lemma, POS, CEFR,
    frequency) but bypasses the CEFR level gate — the candidate is always saved.
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

    def execute(
        self,
        source_id: int,
        surface_form: str,
        context_fragment: str,
    ) -> StoredCandidateDTO:
        source = self._source_repo.get_by_id(source_id)
        if source is None:
            raise SourceNotFoundError(source_id)

        source_text = source.cleaned_text or source.raw_text
        occurrences = max(source_text.lower().count(surface_form.lower()), 1)

        candidate = self._candidate_factory.build(
            source_id=source_id,
            surface_form=surface_form,
            context_fragment=context_fragment,
            occurrences=occurrences,
        )
        saved = self._candidate_repo.create_batch([candidate])[0]
        self._review_status.refresh(source_id)
        return stored_candidate_to_dto(saved)
