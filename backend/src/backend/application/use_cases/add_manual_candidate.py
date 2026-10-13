from __future__ import annotations

import re
from dataclasses import replace
from typing import TYPE_CHECKING

from backend.application.dto.source_dtos import StoredCandidateDTO, stored_candidate_to_dto
from backend.application.utils.candidate_factory import CandidateFactory
from backend.domain.exceptions import (
    InvalidPhraseError,
    SourceHasNoDocumentError,
    SourceNotFoundError,
)
from backend.domain.services.document_layout import DocumentLayout

if TYPE_CHECKING:
    from backend.application.dto.candidate_dtos import SelectionDTO
    from backend.application.utils.review_status_updater import ReviewStatusUpdater
    from backend.domain.ports.candidate_repository import CandidateRepository
    from backend.domain.ports.cefr_classifier import CEFRClassifier
    from backend.domain.ports.document_repository import DocumentRepository
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
        document_repo: DocumentRepository,
        candidate_repo: CandidateRepository,
        text_analyzer: TextAnalyzer,
        cefr_classifier: CEFRClassifier,
        frequency_provider: FrequencyProvider,
        phrasal_verb_detector: PhrasalVerbDetector,
        review_status: ReviewStatusUpdater,
    ) -> None:
        self._source_repo = source_repo
        self._document_repo = document_repo
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
        selection: SelectionDTO,
    ) -> StoredCandidateDTO:
        """The phrase is the selected piece of the document; the target, the picked words in it."""
        if self._source_repo.get_by_id(source_id) is None:
            raise SourceNotFoundError(source_id)
        document = self._document_repo.get(source_id)
        if document is None:
            raise SourceHasNoDocumentError(source_id)
        layout = DocumentLayout(document)
        phrase_position = layout.selected(selection.start, selection.end)
        phrase_start, phrase_end = layout.span(phrase_position)
        target = _words(surface_form).search(layout.text, phrase_start, phrase_end)
        if target is None:
            msg = f"{surface_form!r} is not in the selected phrase"
            raise InvalidPhraseError(msg)
        occurrences = max(layout.text.lower().count(surface_form.lower()), 1)

        candidate = self._candidate_factory.build(
            source_id=source_id,
            surface_form=surface_form,
            context_fragment=layout.fragment(phrase_position),
            occurrences=occurrences,
        )
        candidate = replace(
            candidate,
            phrase_position=phrase_position,
            target_position=layout.position(target.start(), target.end()),
        )
        saved = self._candidate_repo.create_batch([candidate])[0]
        self._review_status.refresh(source_id)
        return stored_candidate_to_dto(saved)


def _words(surface_form: str) -> re.Pattern[str]:
    """The picked words, whatever whitespace stands between them in the document."""
    return re.compile(
        r"\s+".join(re.escape(word) for word in surface_form.split()), re.IGNORECASE,
    )
